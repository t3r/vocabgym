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

    # Get vocab set - first try owned by user
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    response = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )

    vocab_set = response.get('Item')

    # If not owned by user, check if it's a league-assigned set
    if not vocab_set:
        # Query by vocabSetId only (any owner)
        query_response = vocabsets_table.query(
            KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
        )
        sets = query_response.get('Items', [])
        if not sets:
            return build_response(404, {'error': 'Vocabulary set not found'})

        vocab_set = sets[0]

        # Verify user has access via league assignment
        users_table = dynamodb.Table(os.environ['USERS_TABLE'])
        user_response = users_table.get_item(Key={'userId': user_id})
        user = user_response.get('Item', {})
        league_id = user.get('leagueId')

        if not league_id:
            return build_response(403, {'error': 'Access denied'})

        leagues_table = dynamodb.Table(os.environ['LEAGUES_TABLE'])
        league_response = leagues_table.get_item(Key={'leagueId': league_id})
        league = league_response.get('Item', {})
        assigned_ids = league.get('vocabSetIds', [])

        if vocab_set_id not in assigned_ids and league.get('teacherUserId') != user_id:
            return build_response(403, {'error': 'Access denied'})

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

    response_body = {
        'vocabSetId': vocab_set['vocabSetId'],
        'userId': vocab_set['userId'],
        'title': vocab_set.get('title', ''),
        'sourceImageKey': source_image_key,
        'sourceImageUrl': image_url,
        'imageKeys': image_keys,
        'imageUrls': image_urls,
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
    image_key = vocab_set.get('sourceImageKey')
    if image_key:
        try:
            s3_client.delete_object(Bucket=IMAGES_BUCKET, Key=image_key)
        except Exception as e:
            logger.warning(f"Failed to delete image {image_key}: {e}")

    # Delete the vocab set record
    vocabsets_table.delete_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )

    logger.info(json.dumps({
        'event': 'vocab_deleted',
        'vocabSetId': vocab_set_id,
        'userId': user_id,
    }))

    return build_response(200, {
        'message': 'Vocabulary set deleted successfully',
    })
