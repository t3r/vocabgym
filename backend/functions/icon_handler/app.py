"""Icon Handler - Generate robohash identicons for uploaded workbook pages.

Event-driven: triggered via EventBridge when an object is created under the
``images/`` prefix of the images bucket. For each uploaded page it renders a
deterministic identicon in BOTH styles (robots + cats) and caches them in S3.

Design rationale:
- The identicon seed is the FULL image key (one icon per page, 1:1 replacement
  for the original scan). The seed is derived purely from the object key
  (metadata) — never from the image bytes — so the icon has no reproducible
  relationship to the copyrighted workbook content, and no original download is
  needed.
- Both styles are pre-rendered so a user switching their preference (robot/cat)
  sees the change instantly without re-triggering any rendering.
- Idempotent: if both icons already exist for a key, the render is skipped
  (multi-page uploads and event redeliveries are harmless).

Original scans are deleted later by the vocab_crud handler when the set is
approved; this handler only ever writes to the ``identicons/`` prefix.
"""

import hashlib
import io
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

s3_client = boto3.client('s3')

IMAGES_BUCKET = os.environ['IMAGES_BUCKET']

# Robohash sets we support (user-selectable): classic robots + cats.
ICON_SETS = ('set1', 'set4')
ICON_SIZE = int(os.environ.get('ICON_SIZE', '256'))

# Prefix guard: we only render for originals under images/. We NEVER react to
# writes under identicons/ (that would be an infinite loop).
SOURCE_PREFIX = 'images/'
ICON_PREFIX = 'identicons/'


def _seed_for_key(image_key):
    """Derive a deterministic hash seed from the full image key.

    Using the full key (which contains userId/vocabSetId/timestamp) gives one
    unique, stable icon per uploaded page. No image bytes are involved.
    """
    return hashlib.sha256(image_key.encode('utf-8')).hexdigest()


def _icon_key(image_key, roboset):
    """Map an original image key to its identicon key for a given style.

    images/{userId}/{vocabSetId}/{timestamp}-original.jpg
      -> identicons/{userId}/{vocabSetId}/{timestamp}-{roboset}.png
    """
    # Strip the leading source prefix and drop the original file extension.
    rel = image_key[len(SOURCE_PREFIX):] if image_key.startswith(SOURCE_PREFIX) else image_key
    # Remove trailing "-original.<ext>" or any extension, keep the path stem.
    stem = rel.rsplit('.', 1)[0] if '.' in rel.rsplit('/', 1)[-1] else rel
    if stem.endswith('-original'):
        stem = stem[: -len('-original')]
    return f"{ICON_PREFIX}{stem}-{roboset}.png"


def _render_identicon(seed, roboset):
    """Render a single identicon PNG (bytes) for the given seed and style."""
    # Imported lazily so unit tests can exercise key logic without the heavy
    # Pillow/robohash dependency if it is not installed.
    from robohash import Robohash

    rh = Robohash(seed)
    rh.assemble(roboset=roboset, sizex=ICON_SIZE, sizey=ICON_SIZE, format='png')
    buf = io.BytesIO()
    rh.img.save(buf, format='PNG')
    return buf.getvalue()


def _already_rendered(icon_key):
    """Return True if the icon object already exists (idempotency guard)."""
    try:
        s3_client.head_object(Bucket=IMAGES_BUCKET, Key=icon_key)
        return True
    except Exception:
        return False


def _process_image_key(image_key):
    """Render both icon styles for one uploaded page. Returns list of icon keys."""
    # Loop/scope guard: only originals under images/ are processed.
    if not image_key.startswith(SOURCE_PREFIX):
        logger.info('Skipping non-source key: %s', image_key)
        return []
    if image_key.startswith(ICON_PREFIX):
        return []

    seed = _seed_for_key(image_key)
    written = []
    for roboset in ICON_SETS:
        icon_key = _icon_key(image_key, roboset)
        if _already_rendered(icon_key):
            logger.info('Icon already exists, skipping: %s', icon_key)
            written.append(icon_key)
            continue
        png = _render_identicon(seed, roboset)
        s3_client.put_object(
            Bucket=IMAGES_BUCKET,
            Key=icon_key,
            Body=png,
            ContentType='image/png',
        )
        logger.info('Rendered identicon: %s (%d bytes)', icon_key, len(png))
        written.append(icon_key)
    return written


def _extract_image_keys(event):
    """Extract S3 object keys from an EventBridge S3 'Object Created' event.

    Supports the EventBridge detail shape and is tolerant of a direct S3
    notification shape (Records[].s3.object.key) for local testing.
    """
    keys = []

    # EventBridge S3 event: {"detail": {"bucket": {...}, "object": {"key": "..."}}}
    detail = event.get('detail')
    if isinstance(detail, dict):
        obj = detail.get('object', {})
        key = obj.get('key')
        if key:
            keys.append(key)

    # Native S3 notification fallback: {"Records": [{"s3": {"object": {"key": ...}}}]}
    for record in event.get('Records', []) or []:
        try:
            keys.append(record['s3']['object']['key'])
        except (KeyError, TypeError):
            continue

    # S3 keys in events are URL-encoded (spaces as '+', %XX). Decode them.
    import urllib.parse
    return [urllib.parse.unquote_plus(k) for k in keys]


def lambda_handler(event, context):
    """Entry point for EventBridge S3 'Object Created' events."""
    image_keys = _extract_image_keys(event)
    if not image_keys:
        logger.warning('No image keys found in event')
        return {'rendered': []}

    rendered = []
    for image_key in image_keys:
        try:
            rendered.extend(_process_image_key(image_key))
        except Exception:
            # Never fail the whole batch for one bad key; log and continue.
            logger.exception('Failed to render identicon for %s', image_key)

    return {'rendered': rendered}
