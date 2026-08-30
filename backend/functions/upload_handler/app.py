"""Upload Handler - Generate S3 presigned URLs and create initial VocabSet records."""

import json
import logging
import os

import boto3

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    generate_uuid,
    get_timestamp,
    parse_body,
)
from lib.validation import validate_file_upload
from lib.plans import get_plan_set_limit, try_reserve_set_slot, release_set_slot, DEFAULT_PLAN

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
from botocore.config import Config

region = os.environ.get('AWS_REGION', os.environ.get('REGION', 'eu-central-1'))
s3_client = boto3.client(
    's3',
    region_name=region,
    endpoint_url=f'https://s3.{region}.amazonaws.com'
)
dynamodb = boto3.resource('dynamodb')

# Environment variables
IMAGES_BUCKET = os.environ['IMAGES_BUCKET']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
USERS_TABLE = os.environ.get('USERS_TABLE', '')

# Feature flag: block new-set creation at the plan limit. The atomic owned-set
# counter is ALWAYS maintained (race-safe); blocking is enabled once the
# subscription plans go live so existing users are not disrupted early.
ENFORCE_SET_LIMITS = os.environ.get('ENFORCE_SET_LIMITS', 'false').lower() == 'true'


def lambda_handler(event, context):
    """Handle POST /vocab/upload - generate presigned URL for image upload.

    Expected request body:
    {
        "fileName": "workbook_page.jpg",
        "contentType": "image/jpeg",
        "vocabSetId": "uuid" (optional - if provided, adds to existing set)
    }

    Returns:
    {
        "vocabSetId": "uuid",
        "uploadUrl": "presigned-s3-url",
        "imageKey": "images/{userId}/{vocabSetId}/{timestamp}-original.jpg",
        "expiresIn": 300
    }
    """
    logger.info(json.dumps({
        'event': 'upload_request',
        'path': event.get('path'),
        'httpMethod': event.get('httpMethod'),
    }))

    try:
        # Extract user ID from Cognito claims
        user_id = get_user_id_from_event(event)

        # Parse and validate request body
        body = parse_body(event)
        file_name = body.get('fileName', '')
        content_type = body.get('contentType', '')
        existing_vocab_set_id = body.get('vocabSetId')
        target_language = body.get('targetLanguage', '')

        is_valid, error_msg = validate_file_upload(file_name, content_type)
        if not is_valid:
            return build_response(400, {'error': error_msg})

        # Use existing vocabSetId or generate new one
        if existing_vocab_set_id:
            # Verify the set exists and belongs to this user
            table = dynamodb.Table(VOCABSETS_TABLE)
            response = table.get_item(
                Key={'vocabSetId': existing_vocab_set_id, 'userId': user_id}
            )
            if not response.get('Item'):
                return build_response(404, {'error': 'Vocabulary set not found'})
            vocab_set_id = existing_vocab_set_id
        else:
            vocab_set_id = generate_uuid()

        # For a NEW set, reserve an owned-set slot atomically (race-safe).
        # Appending an image to an existing set does not consume a slot.
        slot_reserved = False
        if not existing_vocab_set_id and USERS_TABLE:
            users_table = dynamodb.Table(USERS_TABLE)
            user_resp = users_table.get_item(Key={'userId': user_id})
            plan = (user_resp.get('Item') or {}).get('plan', DEFAULT_PLAN)
            limit = get_plan_set_limit(plan) if ENFORCE_SET_LIMITS else None
            reserved = try_reserve_set_slot(users_table, user_id, limit)
            if not reserved:
                return build_response(403, {
                    'error': 'Set-Limit deines Plans erreicht. Lösche ein Set oder upgrade deinen Plan.',
                    'code': 'PLAN_LIMIT',
                    'plan': plan,
                    'limit': get_plan_set_limit(plan),
                })
            slot_reserved = True

        timestamp = get_timestamp()
        # Whitelist the extension used in the S3 key. The content type is already
        # validated; derive a safe extension from the allowed set only, so a name
        # like "evil.jpg.exe" cannot place an unexpected extension in the key.
        raw_ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''
        extension = raw_ext if raw_ext in ('jpg', 'jpeg', 'png') else 'jpg'
        image_key = f"images/{user_id}/{vocab_set_id}/{timestamp}-original.{extension}"

        # Generate presigned URL for direct upload
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': IMAGES_BUCKET,
                'Key': image_key,
                'ContentType': content_type,
            },
            ExpiresIn=300,  # 5 minutes
        )

        # Create initial VocabSet record or append image to existing set
        table = dynamodb.Table(VOCABSETS_TABLE)
        if not existing_vocab_set_id:
            item_data = {
                'vocabSetId': vocab_set_id,
                'userId': user_id,
                'title': '',
                'sourceImageKey': image_key,
                'imageKeys': [image_key],
                'extractionStatus': 'pending',
                'metadata': {},
                'createdAt': timestamp,
                'updatedAt': timestamp,
                'itemCount': 0,
            }
            if target_language:
                item_data['targetLanguage'] = target_language
            try:
                table.put_item(Item=item_data)
            except Exception:
                # Roll back the reserved slot so a failed create doesn't leak it.
                if slot_reserved and USERS_TABLE:
                    release_set_slot(dynamodb.Table(USERS_TABLE), user_id)
                raise
        else:
            # Append new image key to existing vocab set's imageKeys list
            table.update_item(
                Key={'vocabSetId': vocab_set_id, 'userId': user_id},
                UpdateExpression=(
                    'SET imageKeys = list_append(if_not_exists(imageKeys, :empty), :newKey), '
                    'updatedAt = :ts'
                ),
                ExpressionAttributeValues={
                    ':empty': [],
                    ':newKey': [image_key],
                    ':ts': timestamp,
                },
            )

        logger.info(json.dumps({
            'event': 'upload_created',
            'vocabSetId': vocab_set_id,
            'userId': user_id,
            'imageKey': image_key,
        }))

        return build_response(200, {
            'vocabSetId': vocab_set_id,
            'uploadUrl': presigned_url,
            'imageKey': image_key,
            'expiresIn': 300,
        })

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in upload handler: {e}")
        return build_error_response(e, 'upload_handler')
