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

        timestamp = get_timestamp()
        extension = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else 'jpg'
        image_key = f"images/{user_id}/{vocab_set_id}/{timestamp}-original.{extension}"

        # Generate presigned URL for direct upload
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': IMAGES_BUCKET,
                'Key': image_key,
            },
            ExpiresIn=300,  # 5 minutes
        )

        # Create initial VocabSet record only if new
        if not existing_vocab_set_id:
            table = dynamodb.Table(VOCABSETS_TABLE)
            table.put_item(
                Item={
                    'vocabSetId': vocab_set_id,
                    'userId': user_id,
                    'title': '',
                    'sourceImageKey': image_key,
                    'extractionStatus': 'pending',
                    'metadata': {},
                    'createdAt': timestamp,
                    'updatedAt': timestamp,
                    'itemCount': 0,
                }
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
