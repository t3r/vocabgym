"""Async thumbnail worker.

Consumes SQS messages enqueued by image_handler's POST /images/thumbnail and
generates the comic thumbnail in TWO stages, then caches the PNG in S3:

  Stage 1 (Amazon Nova Pro, eu-central-1 — Converse API):
    Turn the vocabulary meaning into a short ENGLISH comic image prompt. Nova Pro
    is EU-resident and handles the (ambiguous) source-language word well; only a
    generic English motif prompt leaves the EU afterwards — never the German /
    target vocabulary itself.

  Stage 2 (Stability Stable Image Core, us-west-2 — InvokeModel):
    Generate the PNG from that English prompt. No current image model is
    available in the EU, so this single call runs in us-west-2. The prompt is a
    generic motif description with no personal data.

The generated PNG is stored under thumbnails/{lang}/{hash}.png in the eu-central-1
images bucket and served from there — so a word is generated exactly once and
reused for every user.

Idempotency: SQS is at-least-once. Before generating we re-check the S3 cache
(head_object); if the object already exists (a concurrent/duplicate job created
it) we skip the expensive calls.
"""

import base64
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

region = os.environ.get('AWS_REGION', os.environ.get('REGION', 'eu-central-1'))

s3_client = boto3.client(
    's3',
    region_name=region,
    endpoint_url=f'https://s3.{region}.amazonaws.com',
)

# Stage 1: Nova Pro text model — EU region (Frankfurt).
PROMPT_MODEL_ID = os.environ.get('PROMPT_MODEL_ID', 'eu.amazon.nova-pro-v1:0')
bedrock_prompt = boto3.client('bedrock-runtime', region_name=region)

# Stage 2: Stability image model — no EU availability, runs in us-west-2.
# Both modelId and region are env-configurable so a future EU image model is a
# one-line change.
IMAGE_MODEL_ID = os.environ.get('IMAGE_MODEL_ID', 'stability.stable-image-core-v1:1')
IMAGE_MODEL_REGION = os.environ.get('IMAGE_MODEL_REGION', 'us-west-2')
bedrock_image = boto3.client('bedrock-runtime', region_name=IMAGE_MODEL_REGION)

IMAGES_BUCKET = os.environ['IMAGES_BUCKET']

# Stable Image Core prompt limit is ~77 chars; keep Nova Pro's output short.
MAX_IMAGE_PROMPT_LEN = 77

_LANG_NAMES = {'en': 'English', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian'}


def _build_image_prompt(source, target, lang):
    """Stage 1: ask Nova Pro for a short English comic image prompt.

    We give it the German source AND the target word so it can disambiguate the
    meaning, and constrain the output to a short, text-free comic motif. On any
    failure we fall back to a deterministic prompt built from the source word so
    the pipeline still produces something.
    """
    lang_name = _LANG_NAMES.get(lang, lang)
    instruction = (
        "You write short prompts for a text-to-image model that makes simple "
        "comic-style vocabulary thumbnails.\n"
        f"The {lang_name} word is: \"{target}\".\n"
        f"Its German meaning is: \"{source}\".\n"
        "Write ONE English image prompt that depicts the MEANING as a clear, "
        "child-friendly comic illustration. Rules: describe only the concrete "
        "motif, start with 'comic style', no text or letters in the image, "
        f"at most {MAX_IMAGE_PROMPT_LEN} characters. Output ONLY the prompt, no "
        "quotes, no explanation."
    )
    try:
        resp = bedrock_prompt.converse(
            modelId=PROMPT_MODEL_ID,
            messages=[{'role': 'user', 'content': [{'text': instruction}]}],
            inferenceConfig={'maxTokens': 60, 'temperature': 0.7},
        )
        text = resp['output']['message']['content'][0]['text'].strip()
        # Strip accidental wrapping quotes/newlines and hard-cap the length.
        text = text.strip().strip('"').strip().replace('\n', ' ')
        if text:
            return text[:MAX_IMAGE_PROMPT_LEN]
    except Exception as e:
        logger.warning(json.dumps({'event': 'prompt_stage_failed', 'error': str(e)}))

    # Fallback: deterministic, text-free comic prompt from the German meaning.
    return f"comic style illustration of {source}"[:MAX_IMAGE_PROMPT_LEN]


def _generate_image_png(prompt):
    """Stage 2: Stable Image Core → PNG bytes. Returns bytes or None."""
    native_request = {
        'prompt': prompt,
        'aspect_ratio': '1:1',
        'output_format': 'png',
    }
    try:
        resp = bedrock_image.invoke_model(
            modelId=IMAGE_MODEL_ID,
            body=json.dumps(native_request),
        )
        model_response = json.loads(resp['body'].read())
        images = model_response.get('images') or []
        if not images:
            logger.warning(json.dumps({'event': 'image_stage_no_images'}))
            return None
        return base64.b64decode(images[0])
    except Exception as e:
        logger.warning(json.dumps({'event': 'image_stage_failed', 'error': str(e)}))
        return None


def _already_cached(s3_key):
    try:
        s3_client.head_object(Bucket=IMAGES_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', '')
        if code not in ('404', 'NoSuchKey', 'NotFound'):
            logger.warning(f'S3 head_object error: {e}')
        return False


def _process_one(msg):
    source = msg.get('source', '')
    target = msg.get('target', '')
    lang = msg.get('lang', '')
    s3_key = msg.get('s3Key')

    if not (target and lang and s3_key):
        logger.error(json.dumps({'event': 'incomplete_thumbnail_message', 'body': msg}))
        return

    # Idempotency: another delivery may already have generated this.
    if _already_cached(s3_key):
        logger.info(json.dumps({'event': 'thumbnail_already_cached', 's3Key': s3_key}))
        return

    prompt = _build_image_prompt(source, target, lang)
    png = _generate_image_png(prompt)
    if png is None:
        # Raise so SQS retries (transient Bedrock issues), eventually DLQ.
        raise RuntimeError(f'Image generation failed for {s3_key}')

    s3_client.put_object(
        Bucket=IMAGES_BUCKET,
        Key=s3_key,
        Body=png,
        ContentType='image/png',
    )
    logger.info(json.dumps({
        'event': 'thumbnail_generated',
        's3Key': s3_key,
        'lang': lang,
        'promptLen': len(prompt),
    }))


def lambda_handler(event, context):
    """SQS event handler (BatchSize 1, handle multiple defensively)."""
    for record in event.get('Records', []):
        try:
            msg = json.loads(record['body'])
        except (ValueError, KeyError) as e:
            logger.error(f'Malformed SQS message, dropping: {e}')
            continue
        _process_one(msg)
    return {'statusCode': 200}
