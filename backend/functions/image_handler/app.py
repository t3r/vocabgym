"""Image Handler - AI-generated comic thumbnails for vocabulary items.

Routes:
- POST /images/thumbnail {vocabSetId, itemId}
      -> If a thumbnail for this word is already cached in S3, returns a
         presigned URL immediately (200). Otherwise enqueues a generation job
         and returns 202 (status "pending"); the client polls the GET route.
- GET  /images/thumbnail/{vocabSetId}/{itemId}
      -> Poll: returns {status: "ready", url} if cached, else {status: "pending"}.

Design:
- Two-stage generation happens in the async WORKER (worker.py), never in this
  API request — so the API Lambda stays fast (no long-running Bedrock calls in
  the request path). This mirrors the async extraction pipeline (SQS + worker).
- The word to illustrate is resolved server-side from the (owned or league-
  assigned) vocabulary item; the client never sends free text.
- Thumbnails are cached in S3 by (source|target|lang) hash, so a given word is
  generated exactly ONCE and then reused for every user — keeping the number of
  (expensive) LLM/image calls minimal.

Security / abuse protection:
- Owner-or-league resolution identical to polly_handler: every access failure
  returns a uniform 404 (never 403 / cross-owner scan).
- Per-user daily rate limit on real generations (cache misses only).
"""

import datetime
import hashlib
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    get_timestamp,
    parse_body,
    get_path_parameter,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

region = os.environ.get('AWS_REGION', os.environ.get('REGION', 'eu-central-1'))

# S3 needs the regional endpoint for working presigned URLs (see upload_handler)
s3_client = boto3.client(
    's3',
    region_name=region,
    endpoint_url=f'https://s3.{region}.amazonaws.com',
)
dynamodb = boto3.resource('dynamodb')
sqs_client = boto3.client('sqs')

# Environment
IMAGES_BUCKET = os.environ['IMAGES_BUCKET']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
USERS_TABLE = os.environ.get('USERS_TABLE', '')
LEAGUES_TABLE = os.environ.get('LEAGUES_TABLE', '')
THUMBNAIL_USAGE_TABLE = os.environ.get('THUMBNAIL_USAGE_TABLE', '')
THUMBNAIL_QUEUE_URL = os.environ.get('THUMBNAIL_QUEUE_URL', '')

# Supported target languages (same set as the rest of the app)
SUPPORTED_LANGS = {'en', 'fr', 'es', 'it'}

# Image generation is expensive (two LLM/image calls on a cache miss). Cap real
# generations per user per day. Cache hits are never counted.
THUMBNAIL_LIMIT_PER_DAY = int(os.environ.get('THUMBNAIL_LIMIT_PER_DAY', '60'))
THUMBNAIL_USAGE_TTL_SECONDS = 2 * 24 * 60 * 60
PRESIGN_EXPIRES = 3600


def lambda_handler(event, context):
    """Route image requests."""
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(json.dumps({
        'event': 'image_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        if http_method == 'POST' and path.endswith('/images/thumbnail'):
            return handle_request_thumbnail(event, user_id)

        if http_method == 'GET' and '/images/thumbnail/' in path:
            return handle_get_thumbnail(event, user_id)

        return build_response(404, {'error': 'Not found'})
    except Exception as e:
        return build_error_response(e, 'image_handler')


def thumbnail_s3_key(source, target, lang):
    """Cache key for a word's thumbnail.

    Keyed by (source|target|lang) so the SAME word maps to the SAME object for
    ALL users — one generation, reused everywhere. Kept in a module-level helper
    so the worker computes the identical key.
    """
    cache_hash = hashlib.sha256(
        f'{(source or "").strip().lower()}|{(target or "").strip().lower()}|{lang}'.encode('utf-8')
    ).hexdigest()
    return f'thumbnails/{lang}/{cache_hash}.png'


def _resolve_vocab_set(vocab_set_id, user_id):
    """Return the vocab set if the caller may access it (owner or league), else
    None. Mirrors polly_handler: never raises, never distinguishes 403/404."""
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    vs = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    ).get('Item')
    if vs:
        return vs

    # Not owned → resolve deterministically via the caller's league.
    try:
        if not USERS_TABLE:
            return None
        user = dynamodb.Table(USERS_TABLE).get_item(Key={'userId': user_id}).get('Item', {})
        league_id = user.get('leagueId')
        if not (league_id and LEAGUES_TABLE):
            return None
        league = dynamodb.Table(LEAGUES_TABLE).get_item(
            Key={'leagueId': league_id}
        ).get('Item', {})
        assigned_ids = league.get('vocabSetIds', [])
        teacher_user_id = league.get('teacherUserId')
        if vocab_set_id in assigned_ids and teacher_user_id:
            return vocabsets_table.get_item(
                Key={'vocabSetId': vocab_set_id, 'userId': teacher_user_id}
            ).get('Item')
    except Exception as e:
        logger.warning(f'League resolution failed for thumbnail: {e}')
    return None


def _load_item(vocab_set_id, item_id):
    """Load the vocab item, returning (source, target, lang) or None."""
    vocab_set = None  # resolved by caller; kept for clarity
    item = dynamodb.Table(VOCABITEMS_TABLE).get_item(
        Key={'vocabSetId': vocab_set_id, 'itemId': item_id}
    ).get('Item')
    return item


def _presigned_get(s3_key):
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': IMAGES_BUCKET, 'Key': s3_key},
        ExpiresIn=PRESIGN_EXPIRES,
    )


def _is_cached(s3_key):
    try:
        s3_client.head_object(Bucket=IMAGES_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', '')
        if code not in ('404', 'NoSuchKey', 'NotFound'):
            logger.warning(f'S3 head_object error: {e}')
        return False


def _check_and_increment_rate_limit(user_id):
    """Atomic per-user daily counter. Returns True if within the limit."""
    if not THUMBNAIL_USAGE_TABLE:
        return True
    table = dynamodb.Table(THUMBNAIL_USAGE_TABLE)
    window_start = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    expires_at = get_timestamp() + THUMBNAIL_USAGE_TTL_SECONDS
    resp = table.update_item(
        Key={'userId': user_id, 'windowStart': window_start},
        UpdateExpression='ADD #c :one SET expiresAt = if_not_exists(expiresAt, :exp)',
        ExpressionAttributeNames={'#c': 'count'},
        ExpressionAttributeValues={':one': 1, ':exp': expires_at},
        ReturnValues='UPDATED_NEW',
    )
    new_count = int(resp.get('Attributes', {}).get('count', 0))
    return new_count <= THUMBNAIL_LIMIT_PER_DAY


def _resolve_word(event, user_id):
    """Shared: parse vocabSetId/itemId, authorize, load the item + language.

    Returns a tuple (error_response, source, target, lang, vocab_set_id,
    item_id). error_response is None on success.
    """
    body = parse_body(event) if event.get('httpMethod') == 'POST' else {}
    vocab_set_id = body.get('vocabSetId') or get_path_parameter(event, 'vocabSetId')
    item_id = body.get('itemId') or get_path_parameter(event, 'itemId')

    if not vocab_set_id or not item_id:
        return build_response(400, {'error': 'vocabSetId and itemId are required'}), None, None, None, None, None

    vocab_set = _resolve_vocab_set(vocab_set_id, user_id)
    if not vocab_set:
        return build_response(404, {'error': 'Vocabulary set not found'}), None, None, None, None, None

    lang = (vocab_set.get('targetLanguage') or '').lower()
    if lang not in SUPPORTED_LANGS:
        return build_response(400, {'error': f'Unsupported target language: {lang}'}), None, None, None, None, None

    item = _load_item(vocab_set_id, item_id)
    if not item:
        return build_response(404, {'error': 'Vocabulary item not found'}), None, None, None, None, None

    source = item.get('source', item.get('german', ''))
    target = item.get('target', item.get('french', ''))
    if not target:
        return build_response(400, {'error': 'This item has no word to illustrate'}), None, None, None, None, None

    return None, source, target, lang, vocab_set_id, item_id


def handle_request_thumbnail(event, user_id):
    """POST /images/thumbnail — cache-hit shortcut, else enqueue a job."""
    err, source, target, lang, vocab_set_id, item_id = _resolve_word(event, user_id)
    if err:
        return err

    s3_key = thumbnail_s3_key(source, target, lang)

    # Cache hit → return the presigned URL immediately (no generation, no limit).
    if _is_cached(s3_key):
        return build_response(200, {
            'status': 'ready',
            'url': _presigned_get(s3_key),
            'cached': True,
            'expiresIn': PRESIGN_EXPIRES,
        })

    # Cache miss → rate-limit the (expensive) generation, then enqueue.
    if not _check_and_increment_rate_limit(user_id):
        logger.warning(json.dumps({'event': 'thumbnail_rate_limited', 'userId': user_id}))
        return build_response(429, {
            'error': 'Zu viele Bild-Anfragen, bitte kurz warten.'
        })

    if not THUMBNAIL_QUEUE_URL:
        logger.error(json.dumps({'event': 'no_thumbnail_queue', 'vocabSetId': vocab_set_id}))
        return build_response(500, {'error': 'Thumbnail queue not configured'})

    sqs_client.send_message(
        QueueUrl=THUMBNAIL_QUEUE_URL,
        MessageBody=json.dumps({
            'source': source,
            'target': target,
            'lang': lang,
            's3Key': s3_key,
        }),
    )
    logger.info(json.dumps({
        'event': 'thumbnail_enqueued',
        'userId': user_id,
        'vocabSetId': vocab_set_id,
        'itemId': item_id,
        'lang': lang,
    }))

    # 202 Accepted: generation runs async; the client polls the GET route.
    return build_response(202, {'status': 'pending'})


def handle_get_thumbnail(event, user_id):
    """GET /images/thumbnail/{vocabSetId}/{itemId} — poll for the cached image."""
    err, source, target, lang, vocab_set_id, item_id = _resolve_word(event, user_id)
    if err:
        return err

    s3_key = thumbnail_s3_key(source, target, lang)
    if _is_cached(s3_key):
        return build_response(200, {
            'status': 'ready',
            'url': _presigned_get(s3_key),
            'expiresIn': PRESIGN_EXPIRES,
        })
    return build_response(200, {'status': 'pending'})
