"""Async thumbnail worker.

Consumes SQS messages enqueued by image_handler's POST /images/thumbnail and
generates a symbolic comic thumbnail in TWO stages, downscales it, then caches
it in S3:

  Stage 1 (Amazon Nova Pro, eu-central-1 — Converse API):
    Turn the German MEANING into a short ENGLISH comic image prompt. Nova Pro is
    EU-resident; only a generic English motif prompt leaves the EU afterwards —
    never the German/target vocabulary itself. The prompt asks for a symbolic,
    object-focused illustration with no text and no people.

  Stage 2 (Stability Stable Image Core, us-west-2 — InvokeModel):
    Generate the image from that English prompt. No current image model is
    available in the EU, so this single call runs in us-west-2.

The image is downscaled to a small WebP and stored under thumbnails/{hash}.png
(hash of the normalized German meaning) — one image per MEANING, shared across
all target languages, sets and users.

Idempotency: SQS is at-least-once. Before generating we re-check the S3 cache
(head_object); if the object already exists we skip the expensive calls.
"""

import base64
import io
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from PIL import Image

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

# Thumbnails are displayed small; downscale to keep files tiny (~10-40 KB WebP)
# instead of the ~1MP / multi-MB PNG the model returns. This does NOT affect
# Bedrock cost (flat per image) — it saves S3 transfer + load time on mobile.
THUMBNAIL_SIZE = int(os.environ.get('THUMBNAIL_SIZE', '256'))
WEBP_QUALITY = int(os.environ.get('THUMBNAIL_WEBP_QUALITY', '80'))

# Elements to keep OUT of the image. Passed to the model's negative_prompt so it
# applies regardless of the (LLM-written or fallback) positive prompt. Requested
# style: symbolic / object-focused, no text, few or no people.
NEGATIVE_PROMPT = (
    'text, letters, words, writing, captions, labels, watermark, signature, '
    'people, person, human, faces, hands, crowd'
)


def _build_image_prompt(source):
    """Stage 1: ask Nova Pro for a short English comic image prompt.

    Built from the German MEANING only (language-agnostic — the image is shared
    across target languages). Asks for a symbolic, object-focused motif with no
    text and no people. On any failure, falls back to a deterministic prompt.
    """
    instruction = (
        "You write short prompts for a text-to-image model that makes simple "
        "comic-style vocabulary thumbnails.\n"
        f"The concept (in German) is: \"{source}\".\n"
        "Write ONE English image prompt that depicts this concept as a clear, "
        "symbolic, object-focused comic illustration. Rules: start with "
        "'comic style', show the object/scene itself, avoid people, no text or "
        f"letters anywhere in the image, at most {MAX_IMAGE_PROMPT_LEN} "
        "characters. Output ONLY the prompt, no quotes, no explanation."
    )
    try:
        resp = bedrock_prompt.converse(
            modelId=PROMPT_MODEL_ID,
            messages=[{'role': 'user', 'content': [{'text': instruction}]}],
            inferenceConfig={'maxTokens': 60, 'temperature': 0.7},
        )
        text = resp['output']['message']['content'][0]['text'].strip()
        text = text.strip().strip('"').strip().replace('\n', ' ')
        if text:
            return text[:MAX_IMAGE_PROMPT_LEN]
    except Exception as e:
        logger.warning(json.dumps({'event': 'prompt_stage_failed', 'error': str(e)}))

    # Fallback: deterministic, symbolic, text-free comic prompt.
    return f"comic style symbolic icon of {source}, no people"[:MAX_IMAGE_PROMPT_LEN]


def _generate_image_png(prompt):
    """Stage 2: Stable Image Core → raw image bytes (PNG). Returns bytes or None."""
    native_request = {
        'prompt': prompt,
        'negative_prompt': NEGATIVE_PROMPT,
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


def _to_thumbnail_webp(png_bytes):
    """Downscale the generated image to THUMBNAIL_SIZE and encode as WebP.

    Returns WebP bytes, or None if the image can't be processed.
    """
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
        img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='WEBP', quality=WEBP_QUALITY, method=6)
        return out.getvalue()
    except Exception as e:
        logger.warning(json.dumps({'event': 'downscale_failed', 'error': str(e)}))
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
    s3_key = msg.get('s3Key')

    if not (source and s3_key):
        logger.error(json.dumps({'event': 'incomplete_thumbnail_message', 'body': msg}))
        return

    # Idempotency: another delivery may already have generated this.
    if _already_cached(s3_key):
        logger.info(json.dumps({'event': 'thumbnail_already_cached', 's3Key': s3_key}))
        return

    prompt = _build_image_prompt(source)
    png = _generate_image_png(prompt)
    if png is None:
        # Raise so SQS retries (transient Bedrock issues), eventually DLQ.
        raise RuntimeError(f'Image generation failed for {s3_key}')

    webp = _to_thumbnail_webp(png)
    if webp is None:
        raise RuntimeError(f'Thumbnail encoding failed for {s3_key}')

    # Key keeps the .png suffix for backward compatibility with existing URLs,
    # but the body is WebP (browsers detect by content, and we set the type).
    s3_client.put_object(
        Bucket=IMAGES_BUCKET,
        Key=s3_key,
        Body=webp,
        ContentType='image/webp',
    )
    logger.info(json.dumps({
        'event': 'thumbnail_generated',
        's3Key': s3_key,
        'promptLen': len(prompt),
        'bytes': len(webp),
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
