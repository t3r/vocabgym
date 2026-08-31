"""Vocab CRUD Handler - CRUD operations for vocabulary sets and items."""

import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    generate_uuid,
    get_timestamp,
    parse_body,
    get_path_parameter,
)
from lib.validation import validate_vocab_set_data, validate_vocab_items, validate_uuid
from lib.plans import release_set_slot

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
region = os.environ.get('AWS_REGION', os.environ.get('REGION', 'eu-central-1'))
s3_client = boto3.client('s3', region_name=region, endpoint_url=f'https://s3.{region}.amazonaws.com')

# Environment variables
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
IMAGES_BUCKET = os.environ['IMAGES_BUCKET']
USERS_TABLE = os.environ.get('USERS_TABLE', '')

# Identicon styles the icon_handler pre-renders per page. Kept in sync with
# functions/icon_handler/app.py.
VALID_ICON_SETS = ('set1', 'set4')
DEFAULT_ICON_SET = 'set1'
_SOURCE_PREFIX = 'images/'
_ICON_PREFIX = 'identicons/'


def _icon_key_for(image_key, roboset):
    """Map an original image key to its identicon key for a given style.

    Mirrors icon_handler._icon_key:
    images/{userId}/{vocabSetId}/{timestamp}-original.jpg
      -> identicons/{userId}/{vocabSetId}/{timestamp}-{roboset}.png
    """
    if not image_key:
        return None
    rel = image_key[len(_SOURCE_PREFIX):] if image_key.startswith(_SOURCE_PREFIX) else image_key
    last = rel.rsplit('/', 1)[-1]
    stem = rel[: -(len(last.rsplit('.', 1)[-1]) + 1)] if '.' in last else rel
    if stem.endswith('-original'):
        stem = stem[: -len('-original')]
    return f"{_ICON_PREFIX}{stem}-{roboset}.png"


def _list_identicon_url(vocab_set, icon_set):
    """Presigned URL for a set's primary identicon (first page), or None."""
    first_key = vocab_set.get('sourceImageKey') or (vocab_set.get('imageKeys') or [None])[0]
    icon_key = _icon_key_for(first_key, icon_set)
    if not icon_key:
        return None
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': IMAGES_BUCKET, 'Key': icon_key},
            ExpiresIn=3600,
        )
    except Exception as e:
        logger.warning(f"Failed to generate list identicon URL for {icon_key}: {e}")
        return None


def _get_user_icon_set(user_id):
    """Return the user's chosen identicon style ('set1'|'set4'), default set1."""
    if not USERS_TABLE:
        return DEFAULT_ICON_SET
    try:
        user = dynamodb.Table(USERS_TABLE).get_item(Key={'userId': user_id}).get('Item', {})
        pref = (user.get('preferences') or {}).get('identiconSet')
        return pref if pref in VALID_ICON_SETS else DEFAULT_ICON_SET
    except Exception:
        return DEFAULT_ICON_SET


def _delete_original_scans(vocab_set):
    """Delete all original scan objects for a set from S3 (identicons are kept).

    Called on approval: once the user has reviewed and approved the vocabulary,
    the copyrighted original scans are removed; only the generated identicons
    remain.
    """
    source_key = vocab_set.get('sourceImageKey')
    keys = list(vocab_set.get('imageKeys') or [])
    if source_key and source_key not in keys:
        keys.append(source_key)
    for key in keys:
        if not key or not key.startswith(_SOURCE_PREFIX):
            continue
        try:
            s3_client.delete_object(Bucket=IMAGES_BUCKET, Key=key)
        except Exception as e:
            logger.warning(f"Failed to delete original scan {key}: {e}")


def _delete_identicons(vocab_set):
    """Delete all identicons (both styles for every page) of a set from S3."""
    source_key = vocab_set.get('sourceImageKey')
    keys = list(vocab_set.get('imageKeys') or [])
    if source_key and source_key not in keys:
        keys.append(source_key)
    for key in keys:
        for roboset in VALID_ICON_SETS:
            icon_key = _icon_key_for(key, roboset)
            if not icon_key:
                continue
            try:
                s3_client.delete_object(Bucket=IMAGES_BUCKET, Key=icon_key)
            except Exception as e:
                logger.warning(f"Failed to delete identicon {icon_key}: {e}")


def lambda_handler(event, context):
    """Route requests to appropriate handler based on HTTP method and path.

    Routes:
    - GET /vocab: List all vocab sets for user
    - GET /vocab/{vocabSetId}: Get specific vocab set with items
    - PUT /vocab/{vocabSetId}: Update/approve vocab set
    - DELETE /vocab/{vocabSetId}: Delete vocab set and all items
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    path_params = event.get('pathParameters') or {}

    logger.info(json.dumps({
        'event': 'vocab_crud_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        if http_method == 'GET' and not path_params.get('vocabSetId'):
            return handle_list(event, user_id)
        elif http_method == 'GET' and path_params.get('vocabSetId'):
            return handle_get(event, user_id)
        elif http_method == 'PUT' and path_params.get('vocabSetId'):
            return handle_update(event, user_id)
        elif http_method == 'DELETE' and path_params.get('vocabSetId'):
            return handle_delete(event, user_id)
        else:
            return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in vocab CRUD handler: {e}")
        return build_error_response(e, 'vocab_crud_handler')


def handle_list(event, user_id):
    """Handle GET /vocab - List all vocabulary sets for the user.

    Returns vocabulary sets sorted by creation date (newest first).
    """
    table = dynamodb.Table(VOCABSETS_TABLE)

    response = table.query(
        IndexName='userId-createdAt-index',
        KeyConditionExpression=Key('userId').eq(user_id),
        ScanIndexForward=False,  # Newest first
    )

    vocab_sets = response.get('Items', [])

    # Enrich with progress data
    progress_table = dynamodb.Table(os.environ['PROGRESS_TABLE'])
    icon_set = _get_user_icon_set(user_id)
    enriched_sets = []
    for vs in vocab_sets:
        vocab_set_id = vs['vocabSetId']
        item_count = int(vs.get('itemCount', 0))

        # Query progress for this set
        mastery = 0
        last_practiced = 0
        if item_count > 0:
            progress_key = f"{user_id}#{vocab_set_id}"
            prog_response = progress_table.query(
                KeyConditionExpression=Key('progressKey').eq(progress_key)
            )
            progress_items = prog_response.get('Items', [])

            if progress_items:
                total_correct = sum(int(p.get('correctCount', 0)) for p in progress_items)
                total_attempts = total_correct + sum(int(p.get('incorrectCount', 0)) for p in progress_items)
                mastery = int((total_correct / total_attempts * 100) if total_attempts > 0 else 0)
                last_practiced = max(int(p.get('lastPracticedAt', 0)) for p in progress_items)

        enriched_sets.append({
            'vocabSetId': vocab_set_id,
            'title': vs.get('title', ''),
            'extractionStatus': vs.get('extractionStatus', 'pending'),
            'metadata': vs.get('metadata', {}),
            'itemCount': item_count,
            'createdAt': vs.get('createdAt', 0),
            'updatedAt': vs.get('updatedAt', 0),
            'mastery': mastery,
            'lastPracticedAt': last_practiced,
            'identiconSet': icon_set,
            'identiconUrl': _list_identicon_url(vs, icon_set),
            'sourceLanguage': vs.get('sourceLanguage', 'de'),
        })

    logger.info(json.dumps({
        'event': 'vocab_list',
        'userId': user_id,
        'count': len(vocab_sets),
    }))

    return build_response(200, {
        'vocabSets': enriched_sets,
        'count': len(enriched_sets),
    })


def handle_get(event, user_id):
    """Handle GET /vocab/{vocabSetId} - Get a specific vocabulary set with items."""
    vocab_set_id = get_path_parameter(event, 'vocabSetId')

    is_valid, err = validate_uuid(vocab_set_id, 'vocabSetId')
    if not is_valid:
        return build_response(400, {'error': err})

    # Get vocab set - first try the set owned by the caller.
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    response = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )
    vocab_set = response.get('Item')

    # If the caller does not own it, the only legitimate access is via a league
    # the caller belongs to. Resolve access WITHOUT revealing whether the set
    # exists: we never scan the set's partition for arbitrary owners, and every
    # access failure returns a uniform 404 (never 403), so an attacker cannot
    # probe for the existence of other users' set IDs.
    if not vocab_set:
        not_found = build_response(404, {'error': 'Vocabulary set not found'})

        users_table = dynamodb.Table(os.environ['USERS_TABLE'])
        user = users_table.get_item(Key={'userId': user_id}).get('Item', {})
        league_id = user.get('leagueId')
        if not league_id:
            return not_found

        leagues_table = dynamodb.Table(os.environ['LEAGUES_TABLE'])
        league = leagues_table.get_item(Key={'leagueId': league_id}).get('Item', {})
        assigned_ids = league.get('vocabSetIds', [])
        teacher_user_id = league.get('teacherUserId')

        # The set must be assigned to the caller's league. The owner of a
        # league set is the league's teacher, so we can fetch it deterministically
        # by its known owner instead of querying across all owners.
        if vocab_set_id not in assigned_ids or not teacher_user_id:
            return not_found

        owned = vocabsets_table.get_item(
            Key={'vocabSetId': vocab_set_id, 'userId': teacher_user_id}
        ).get('Item')
        if not owned:
            return not_found
        vocab_set = owned

    # Get items
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    items_response = items_table.query(
        KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
    )

    items = items_response.get('Items', [])
    items.sort(key=lambda x: x.get('order', 0))

    # Generate presigned URL for source image
    image_url = None
    source_image_key = vocab_set.get('sourceImageKey', '')
    if source_image_key:
        try:
            image_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': IMAGES_BUCKET, 'Key': source_image_key},
                ExpiresIn=3600,
            )
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL: {e}")

    # Generate presigned URLs for all images in the set
    image_keys = vocab_set.get('imageKeys') or ([source_image_key] if source_image_key else [])
    image_urls = []
    for key in image_keys:
        if key:
            try:
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': IMAGES_BUCKET, 'Key': key},
                    ExpiresIn=3600,
                )
                image_urls.append(url)
            except Exception as e:
                logger.warning(f"Failed to generate presigned URL for {key}: {e}")

    # Generate presigned URLs for the identicons (one per page), in the caller's
    # preferred style. These are the persistent visual identity of the set and
    # remain valid after the originals are deleted on approval.
    icon_set = _get_user_icon_set(user_id)
    identicon_urls = []
    for key in image_keys:
        icon_key = _icon_key_for(key, icon_set)
        if not icon_key:
            continue
        try:
            identicon_urls.append(
                s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': IMAGES_BUCKET, 'Key': icon_key},
                    ExpiresIn=3600,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to generate identicon URL for {icon_key}: {e}")

    response_body = {
        'vocabSetId': vocab_set['vocabSetId'],
        'userId': vocab_set['userId'],
        'title': vocab_set.get('title', ''),
        'sourceImageKey': source_image_key,
        'sourceImageUrl': image_url,
        'imageKeys': image_keys,
        'imageUrls': image_urls,
        'identiconSet': icon_set,
        'identiconUrl': identicon_urls[0] if identicon_urls else None,
        'identiconUrls': identicon_urls,
        'extractionStatus': vocab_set.get('extractionStatus', 'pending'),
        'metadata': vocab_set.get('metadata', {}),
        'itemCount': len(items),
        'createdAt': vocab_set.get('createdAt', 0),
        'updatedAt': vocab_set.get('updatedAt', 0),
        'items': [
            {
                'itemId': item['itemId'],
                'source': item.get('source', item.get('german', '')),
                'target': item.get('target', item.get('french', '')),
                'notes': item.get('notes', ''),
                'order': item.get('order', 0),
                'isActive': item.get('isActive', True),
                **(({'imageKey': item['imageKey']} if item.get('imageKey') else {})),
            }
            for item in items
        ],
    }

    # Include targetLanguage if it exists on the vocab set
    if vocab_set.get('targetLanguage'):
        response_body['targetLanguage'] = vocab_set['targetLanguage']

    # Source language: existing sets have no field → default to German.
    response_body['sourceLanguage'] = vocab_set.get('sourceLanguage', 'de')

    return build_response(200, response_body)


def handle_update(event, user_id):
    """Handle PUT /vocab/{vocabSetId} - Update vocabulary set metadata and items.

    Expected body:
    {
        "title": "Chapter 3: At Home",
        "metadata": {"chapter": "3", "pageNumber": 42, "topic": "Household"},
        "items": [
            {"itemId": "uuid", "german": "das Haus", "french": "la maison"},
            {"german": "die Schule", "french": "l'école"}  // new item (no itemId)
        ],
        "approve": true  // optional, changes status to "approved"
    }
    """
    vocab_set_id = get_path_parameter(event, 'vocabSetId')

    is_valid, err = validate_uuid(vocab_set_id, 'vocabSetId')
    if not is_valid:
        return build_response(400, {'error': err})

    body = parse_body(event)

    # Validate vocab set data
    is_valid, err = validate_vocab_set_data(body)
    if not is_valid:
        return build_response(400, {'error': err})

    # Verify ownership
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    response = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )

    if not response.get('Item'):
        return build_response(404, {'error': 'Vocabulary set not found'})

    timestamp = get_timestamp()

    # Update vocab set metadata
    update_expr_parts = ['updatedAt = :ts']
    expr_values = {':ts': timestamp}

    if 'title' in body:
        update_expr_parts.append('title = :title')
        expr_values[':title'] = body['title']

    if 'metadata' in body:
        update_expr_parts.append('metadata = :metadata')
        expr_values[':metadata'] = body['metadata']

    if 'targetLanguage' in body:
        update_expr_parts.append('targetLanguage = :tl')
        expr_values[':tl'] = body['targetLanguage']

    if body.get('approve'):
        update_expr_parts.append('extractionStatus = :status')
        expr_values[':status'] = 'approved'

    # Update items if provided
    items = body.get('items')
    if items is not None:
        is_valid, err = validate_vocab_items(items)
        if not is_valid:
            return build_response(400, {'error': err})

        # Delete existing items and replace with new ones
        items_table = dynamodb.Table(VOCABITEMS_TABLE)

        # Get and delete existing items
        existing_items = items_table.query(
            KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
        )
        with items_table.batch_writer() as batch:
            for existing in existing_items.get('Items', []):
                batch.delete_item(
                    Key={
                        'vocabSetId': vocab_set_id,
                        'itemId': existing['itemId'],
                    }
                )

        # Write new items
        with items_table.batch_writer() as batch:
            for i, item in enumerate(items):
                item_id = item.get('itemId') or generate_uuid()
                source_text = item.get('source', item.get('german', '')).strip()
                target_text = item.get('target', item.get('french', '')).strip()
                batch.put_item(
                    Item={
                        'vocabSetId': vocab_set_id,
                        'itemId': item_id,
                        'source': source_text,
                        'target': target_text,
                        'notes': item.get('notes', ''),
                        'order': i + 1,
                        'createdAt': timestamp,
                        'updatedAt': timestamp,
                        'isActive': item.get('isActive', True),
                    }
                )

        update_expr_parts.append('itemCount = :count')
        expr_values[':count'] = len(items)

    # Apply updates to vocab set
    update_expression = 'SET ' + ', '.join(update_expr_parts)
    vocabsets_table.update_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expr_values,
    )

    # On approval, delete the copyrighted original scans. The generated
    # identicons (identicons/ prefix) are kept as the set's visual identity.
    # Rendering never depends on the originals, so this is safe.
    if body.get('approve'):
        _delete_original_scans(response['Item'])

    logger.info(json.dumps({
        'event': 'vocab_updated',
        'vocabSetId': vocab_set_id,
        'userId': user_id,
        'approved': body.get('approve', False),
    }))

    return build_response(200, {
        'vocabSetId': vocab_set_id,
        'message': 'Vocabulary set updated successfully',
    })


def handle_delete(event, user_id):
    """Handle DELETE /vocab/{vocabSetId} - Delete vocabulary set and all associated data."""
    vocab_set_id = get_path_parameter(event, 'vocabSetId')

    is_valid, err = validate_uuid(vocab_set_id, 'vocabSetId')
    if not is_valid:
        return build_response(400, {'error': err})

    # Verify ownership
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    response = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )

    vocab_set = response.get('Item')
    if not vocab_set:
        return build_response(404, {'error': 'Vocabulary set not found'})

    # Delete all vocab items
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    items_response = items_table.query(
        KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
    )

    with items_table.batch_writer() as batch:
        for item in items_response.get('Items', []):
            batch.delete_item(
                Key={
                    'vocabSetId': vocab_set_id,
                    'itemId': item['itemId'],
                }
            )

    # Delete source image from S3
    # Delete all original scans (multi-page) and all identicons (both styles per
    # page) from S3. On set deletion nothing should linger in the bucket.
    _delete_original_scans(vocab_set)
    _delete_identicons(vocab_set)

    # Delete the vocab set record
    vocabsets_table.delete_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )

    # Release the owned-set slot (race-safe, never below zero).
    if USERS_TABLE:
        release_set_slot(dynamodb.Table(USERS_TABLE), user_id)

    logger.info(json.dumps({
        'event': 'vocab_deleted',
        'vocabSetId': vocab_set_id,
        'userId': user_id,
    }))

    return build_response(200, {
        'message': 'Vocabulary set deleted successfully',
    })
