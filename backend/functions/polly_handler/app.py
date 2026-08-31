"""Polly Handler - Text-to-Speech pronunciation for vocabulary items.

Routes:
- GET  /tts/voices?lang=<fr|en|es|it>  -> available Polly (standard-engine)
      voices for the language, grouped by accent (LanguageCode).
- POST /tts/synthesize {vocabSetId, itemId, voiceId}
      -> synthesizes the target word of the given (owned) vocab item with the
      requested voice, caches the MP3 in S3 and returns a presigned URL.

Security / abuse protection:
- The synthesize endpoint never accepts free text. It reads the word to speak
  from DynamoDB (VocabItems.target) after verifying ownership of the parent
  VocabSet. Only the caller's own, existing vocabulary can be synthesized.
- The requested VoiceId is validated against the voices Polly reports for the
  language (standard engine).
- Per-user rate limit of 60 real syntheses (cache misses only) per hour.
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
    get_query_parameter,
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
polly_client = boto3.client('polly', region_name=region)
dynamodb = boto3.resource('dynamodb')

# Environment variables
IMAGES_BUCKET = os.environ['IMAGES_BUCKET']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
TTS_USAGE_TABLE = os.environ.get('TTS_USAGE_TABLE', '')
USERS_TABLE = os.environ.get('USERS_TABLE', '')
LEAGUES_TABLE = os.environ.get('LEAGUES_TABLE', '')

# Supported target languages -> Polly LanguageCode prefix
LANG_PREFIX = {
    'en': 'en',
    'fr': 'fr',
    'es': 'es',
    'it': 'it',
}

# Human-readable accent names for common Polly LanguageCodes
ACCENT_NAMES = {
    'en-US': 'Amerikanisch (en-US)',
    'en-GB': 'Britisch (en-GB)',
    'en-AU': 'Australisch (en-AU)',
    'en-GB-WLS': 'Walisisch (en-GB-WLS)',
    'en-IN': 'Indisch (en-IN)',
    'en-NZ': 'Neuseeländisch (en-NZ)',
    'en-ZA': 'Südafrikanisch (en-ZA)',
    'fr-FR': 'Französisch (fr-FR)',
    'fr-CA': 'Kanadisch (fr-CA)',
    'fr-BE': 'Belgisch (fr-BE)',
    'es-ES': 'Spanien (es-ES)',
    'es-US': 'Amerikanisch (es-US)',
    'es-MX': 'Mexikanisch (es-MX)',
    'it-IT': 'Italienisch (it-IT)',
}

# Rate limit: real syntheses (cache misses) per user per hour
RATE_LIMIT_PER_HOUR = 60
# Max characters to synthesize (a single vocab word/phrase)
MAX_TTS_TEXT_LENGTH = 200
# Usage counter TTL (seconds) — a bit over an hour so the window can expire
USAGE_TTL_SECONDS = 2 * 60 * 60
# Presigned URL validity
PRESIGN_EXPIRES = 3600

# Voice cache per Lambda container: {lang: {voiceId: LanguageCode}}
_voice_cache = {}


def lambda_handler(event, context):
    """Route TTS requests."""
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(json.dumps({
        'event': 'tts_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        if http_method == 'GET' and '/tts/voices' in path:
            return handle_voices(event, user_id)
        elif http_method == 'POST' and '/tts/synthesize' in path:
            return handle_synthesize(event, user_id)
        else:
            return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in polly handler: {e}")
        return build_error_response(e, 'polly_handler')


def _describe_standard_voices(lang):
    """Return standard-engine voices for a language as list of Polly voice dicts.

    Args:
        lang: short language code (fr|en|es|it)

    Returns:
        list of Polly voice dicts (Id, Name, Gender, LanguageCode, SupportedEngines)
    """
    prefix = LANG_PREFIX.get(lang)
    if not prefix:
        return []

    voices = []
    next_token = None
    while True:
        kwargs = {}
        if next_token:
            kwargs['NextToken'] = next_token
        resp = polly_client.describe_voices(**kwargs)
        for v in resp.get('Voices', []):
            language_code = v.get('LanguageCode', '')
            if not language_code.startswith(prefix + '-') and language_code != prefix:
                continue
            if 'standard' not in [e.lower() for e in v.get('SupportedEngines', [])]:
                continue
            voices.append(v)
        next_token = resp.get('NextToken')
        if not next_token:
            break

    return voices


def _get_allowed_voice_ids(lang):
    """Return a dict {voiceId: LanguageCode} of allowed standard voices for lang.

    Cached per Lambda container.
    """
    if lang in _voice_cache:
        return _voice_cache[lang]

    mapping = {}
    for v in _describe_standard_voices(lang):
        mapping[v['Id']] = v.get('LanguageCode', '')
    _voice_cache[lang] = mapping
    return mapping


def handle_voices(event, user_id):
    """Handle GET /tts/voices?lang=<code> - list standard voices grouped by accent."""
    lang = (get_query_parameter(event, 'lang', '') or '').lower()

    if lang not in LANG_PREFIX:
        return build_response(400, {
            'error': f"Unsupported language: {lang}. Allowed: {', '.join(sorted(LANG_PREFIX))}"
        })

    voices = _describe_standard_voices(lang)

    # Group by LanguageCode (accent)
    groups = {}
    for v in voices:
        language_code = v.get('LanguageCode', '')
        group = groups.setdefault(language_code, {
            'languageCode': language_code,
            'accentName': ACCENT_NAMES.get(language_code, language_code),
            'voices': [],
        })
        group['voices'].append({
            'voiceId': v.get('Id', ''),
            'name': v.get('Name', v.get('Id', '')),
            'gender': v.get('Gender', ''),
        })

    # Stable ordering: by accent name, voices by name
    accents = sorted(groups.values(), key=lambda g: g['accentName'])
    for g in accents:
        g['voices'].sort(key=lambda x: x['name'])

    logger.info(json.dumps({
        'event': 'tts_voices',
        'userId': user_id,
        'lang': lang,
        'accentCount': len(accents),
    }))

    return build_response(200, {'lang': lang, 'accents': accents})


def _speakable_text(target):
    """Extract the text to speak from a vocab item's target field.

    Keeps the article, but for multiple meanings (separated by ';' or ',')
    only the first part is used.
    """
    if not target:
        return ''
    text = target.strip()
    # Cut at the first ';' or ',' — take the first meaning only
    for sep in (';', ','):
        idx = text.find(sep)
        if idx != -1:
            text = text[:idx]
    return text.strip()


def _check_and_increment_rate_limit(user_id):
    """Increment the per-user hourly counter. Returns True if within limit.

    Only call this for real syntheses (cache misses).
    """
    if not TTS_USAGE_TABLE:
        return True

    table = dynamodb.Table(TTS_USAGE_TABLE)
    window_start = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H')
    expires_at = get_timestamp() + USAGE_TTL_SECONDS

    resp = table.update_item(
        Key={'userId': user_id, 'windowStart': window_start},
        UpdateExpression='ADD #c :one SET expiresAt = if_not_exists(expiresAt, :exp)',
        ExpressionAttributeNames={'#c': 'count'},
        ExpressionAttributeValues={':one': 1, ':exp': expires_at},
        ReturnValues='UPDATED_NEW',
    )
    new_count = int(resp.get('Attributes', {}).get('count', 0))
    return new_count <= RATE_LIMIT_PER_HOUR


def handle_synthesize(event, user_id):
    """Handle POST /tts/synthesize - synthesize an owned vocab item's target word.

    Expected body: { "vocabSetId": "uuid", "itemId": "uuid", "voiceId": "Amy" }
    """
    body = parse_body(event)
    vocab_set_id = body.get('vocabSetId')
    item_id = body.get('itemId')
    voice_id = body.get('voiceId')

    if not vocab_set_id or not item_id:
        return build_response(400, {'error': 'vocabSetId and itemId are required'})
    if not voice_id:
        return build_response(400, {'error': 'voiceId is required'})

    # Ownership check: the vocab set must exist AND belong to this user, OR be a
    # set assigned to the caller's league (league members practise the teacher's
    # sets). Same owned-or-league resolution as practice_handler — without it,
    # pronouncing a word in a league set returned a 404 for students.
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    vs_resp = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )
    vocab_set = vs_resp.get('Item')

    if not vocab_set:
        # Not owned by caller → resolve via the caller's league deterministically
        # (fetch league, verify the set is assigned, then load by teacher owner).
        # Every failure — including any lookup error — returns a uniform 404
        # (never 403 / cross-owner scan, never a 500 that leaks internals).
        vocab_set = None
        try:
            league_id = None
            if USERS_TABLE:
                users_table = dynamodb.Table(USERS_TABLE)
                user = users_table.get_item(Key={'userId': user_id}).get('Item', {})
                league_id = user.get('leagueId')

            if league_id and LEAGUES_TABLE:
                leagues_table = dynamodb.Table(LEAGUES_TABLE)
                league = leagues_table.get_item(Key={'leagueId': league_id}).get('Item', {})
                assigned_ids = league.get('vocabSetIds', [])
                teacher_user_id = league.get('teacherUserId')

                if vocab_set_id in assigned_ids and teacher_user_id:
                    vs_resp = vocabsets_table.get_item(
                        Key={'vocabSetId': vocab_set_id, 'userId': teacher_user_id}
                    )
                    vocab_set = vs_resp.get('Item')
        except Exception as e:
            logger.warning(f'League resolution failed for TTS: {e}')
            vocab_set = None

        if not vocab_set:
            return build_response(404, {'error': 'Vocabulary set not found'})

    lang = (vocab_set.get('targetLanguage') or '').lower()
    if lang not in LANG_PREFIX:
        return build_response(400, {'error': f'Unsupported target language: {lang}'})

    # Load the vocab item and its target word
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    item_resp = items_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'itemId': item_id}
    )
    item = item_resp.get('Item')
    if not item:
        return build_response(404, {'error': 'Vocabulary item not found'})

    text = _speakable_text(item.get('target', ''))
    if not text:
        return build_response(400, {'error': 'This item has no target word to pronounce'})
    if len(text) > MAX_TTS_TEXT_LENGTH:
        text = text[:MAX_TTS_TEXT_LENGTH]

    # Validate voice against the allowed standard voices for this language
    allowed_voices = _get_allowed_voice_ids(lang)
    if voice_id not in allowed_voices:
        return build_response(400, {
            'error': f'Invalid voice for language {lang}: {voice_id}'
        })

    # Cache lookup: key = sha256(text|voiceId)
    cache_hash = hashlib.sha256(f'{text}|{voice_id}'.encode('utf-8')).hexdigest()
    s3_key = f'tts/{lang}/{cache_hash}.mp3'

    cached = False
    try:
        s3_client.head_object(Bucket=IMAGES_BUCKET, Key=s3_key)
        cached = True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code not in ('404', 'NoSuchKey', 'NotFound'):
            logger.warning(f'S3 head_object error: {e}')
        cached = False

    if not cached:
        # Rate limit only counts real syntheses
        within_limit = _check_and_increment_rate_limit(user_id)
        if not within_limit:
            logger.warning(json.dumps({
                'event': 'tts_rate_limited',
                'userId': user_id,
            }))
            return build_response(429, {
                'error': 'Zu viele Aussprache-Anfragen, bitte kurz warten.'
            })

        # Synthesize with Polly (standard engine, mp3)
        try:
            speech = polly_client.synthesize_speech(
                Engine='standard',
                OutputFormat='mp3',
                VoiceId=voice_id,
                Text=text,
            )
        except ClientError as e:
            logger.warning(f'Polly synthesize error: {e}')
            return build_response(502, {'error': 'Sprachsynthese fehlgeschlagen.'})

        audio_stream = speech.get('AudioStream')
        if audio_stream is None:
            return build_response(502, {'error': 'Sprachsynthese lieferte kein Audio.'})

        s3_client.put_object(
            Bucket=IMAGES_BUCKET,
            Key=s3_key,
            Body=audio_stream.read(),
            ContentType='audio/mpeg',
        )

    audio_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': IMAGES_BUCKET, 'Key': s3_key},
        ExpiresIn=PRESIGN_EXPIRES,
    )

    logger.info(json.dumps({
        'event': 'tts_synthesized',
        'userId': user_id,
        'vocabSetId': vocab_set_id,
        'itemId': item_id,
        'lang': lang,
        'voiceId': voice_id,
        'cached': cached,
    }))

    return build_response(200, {
        'audioUrl': audio_url,
        'cached': cached,
        'expiresIn': PRESIGN_EXPIRES,
    })
