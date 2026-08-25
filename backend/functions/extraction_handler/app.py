"""Extraction Handler - Process workbook images with Textract and extract vocabulary."""

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
    get_path_parameter,
)
from lib.validation import validate_uuid
from lib.languages import get_language, DEFAULT_TARGET_LANGUAGE

from textract_parser import TextractParser

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
s3_client = boto3.client('s3')
textract_client = boto3.client('textract')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

# Environment variables
IMAGES_BUCKET = os.environ['IMAGES_BUCKET']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
OPENAI_API_KEY_SECRET = os.environ.get('OPENAI_API_KEY_SECRET', '')

# Cache for OpenAI API key
_openai_api_key = None


def get_openai_api_key():
    """Retrieve OpenAI API key from Secrets Manager."""
    global _openai_api_key
    if _openai_api_key:
        return _openai_api_key

    try:
        response = secrets_client.get_secret_value(SecretId=OPENAI_API_KEY_SECRET)
        _openai_api_key = response['SecretString']
        return _openai_api_key
    except Exception as e:
        logger.error(f"Failed to retrieve OpenAI API key: {e}")
        return None


def extract_with_textract(image_key):
    """Use AWS Textract to analyze the document for tables.

    Args:
        image_key: S3 object key for the image

    Returns:
        tuple: (vocab_pairs, confidence) where vocab_pairs is list of {source, target}
    """
    logger.info(json.dumps({
        'event': 'textract_start',
        'imageKey': image_key,
    }))

    response = textract_client.analyze_document(
        Document={
            'S3Object': {
                'Bucket': IMAGES_BUCKET,
                'Name': image_key,
            }
        },
        FeatureTypes=['TABLES']
    )

    parser = TextractParser(response)
    vocab_pairs = parser.extract_vocabulary_pairs()

    # Calculate average confidence
    if vocab_pairs:
        avg_confidence = sum(p.get('confidence', 0) for p in vocab_pairs) / len(vocab_pairs)
    else:
        avg_confidence = 0.0

    logger.info(json.dumps({
        'event': 'textract_complete',
        'pairsFound': len(vocab_pairs),
        'avgConfidence': round(avg_confidence, 2),
    }))

    return vocab_pairs, avg_confidence


def extract_with_openai(image_key):
    """Fallback: Use OpenAI Vision API to extract vocabulary.

    Args:
        image_key: S3 object key for the image

    Returns:
        list: List of {source, target} vocabulary pairs
    """
    api_key = get_openai_api_key()
    if not api_key:
        logger.error("OpenAI API key not available")
        return []

    try:
        import openai

        # Generate a presigned URL for OpenAI to access the image
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': IMAGES_BUCKET, 'Key': image_key},
            ExpiresIn=300,
        )

        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are analyzing a page from a German school workbook for "
                        "learning French vocabulary. Extract all vocabulary pairs from "
                        "any tables or lists on this page."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract all German-French vocabulary pairs from this "
                                "workbook page. Return ONLY a JSON array with this exact "
                                "structure:\n"
                                '[{"source": "das Haus", "target": "la maison"}]\n\n'
                                "Rules:\n"
                                "1. Preserve accents and special characters exactly\n"
                                "2. Ignore headers, page numbers, and instructions\n"
                                "3. Include articles (der/die/das, le/la/les) if present\n"
                                "4. Return only the JSON array, no additional text"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": presigned_url},
                        },
                    ],
                },
            ],
            max_tokens=4096,
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON from response (handle markdown code blocks)
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        vocab_pairs = json.loads(content)

        logger.info(json.dumps({
            'event': 'openai_extraction_complete',
            'pairsFound': len(vocab_pairs),
        }))

        # Add confidence score for OpenAI results
        for pair in vocab_pairs:
            pair['confidence'] = 0.85  # OpenAI results generally reliable

        return vocab_pairs

    except Exception as e:
        logger.exception(f"OpenAI extraction failed: {e}")
        return []


def store_vocab_items(vocab_set_id, vocab_pairs):
    """Store extracted vocabulary items in DynamoDB.

    Args:
        vocab_set_id: The vocabulary set ID
        vocab_pairs: List of {source, target, confidence} dicts

    Returns:
        int: Number of items stored
    """
    table = dynamodb.Table(VOCABITEMS_TABLE)
    timestamp = get_timestamp()

    with table.batch_writer() as batch:
        for i, pair in enumerate(vocab_pairs):
            item_id = generate_uuid()
            source_text = pair.get('source', pair.get('german', '')).strip()
            target_text = pair.get('target', pair.get('french', '')).strip()
            batch.put_item(
                Item={
                    'vocabSetId': vocab_set_id,
                    'itemId': item_id,
                    'source': _strip_phonetics(source_text),
                    'target': _strip_phonetics(target_text),
                    'notes': pair.get('notes', ''),
                    'order': i + 1,
                    'confidence': int(pair.get('confidence', 0) * 100),
                    'createdAt': timestamp,
                    'updatedAt': timestamp,
                    'isActive': True,
                }
            )

    return len(vocab_pairs)


def _strip_phonetics(text):
    """Remove phonetic transcriptions in brackets from text.

    Handles [phonetics], (phonetics), and various unicode bracket types.
    Also strips IPA-style transcriptions like /fɔnetik/.
    """
    import re
    if not text:
        return text

    original = text

    # Remove content between ASCII square brackets
    text = re.sub(r'\[.*?\]', '', text)
    # Remove content between ASCII parentheses that look phonetic (no spaces, has special chars)
    text = re.sub(r'\([^)]*[ēĒõãɛɔ][^)]*\)', '', text)
    # Remove content between various unicode brackets
    text = re.sub(r'[\uff3b\u3010\u300c].*?[\uff3d\u3011\u300d]', '', text)
    # Remove content between forward slashes (IPA)
    text = re.sub(r'/[^/]+/', '', text)
    # Fallback: remove anything after a semicolon followed by bracket-like content
    # Handles cases where ; separates from phonetic: "un mot; [phonetic]"

    # Nuclear option: if none of the above worked, try to detect and strip
    # phonetic content that starts with common phonetic markers
    # Pattern: word(s) followed by bracket-like content with phonetic chars
    text = re.sub(r'\s*[\[\(\{][\s\S]*?[\]\)\}]', '', text)

    # If we still have the same text (nothing was stripped), try to catch
    # non-ASCII brackets by removing everything after the last letter+space
    # that's followed by something that looks phonetic
    if text == original:
        # Match: any bracket-like start char followed by phonetic-looking content
        text = re.sub(r'\s*[^\w\s,;:\-\'éèêëàâùûôîïçœæ].*$', '', text)

    # Clean up whitespace and trailing semicolons
    text = re.sub(r'\s*;\s*$', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text if text else original  # Don't return empty string



def lambda_handler(event, context):
    """Handle vocabulary extraction requests.

    Routes:
    - POST /vocab/process: Trigger extraction for an uploaded image
    - GET /vocab/extraction/{vocabSetId}: Get extraction results/status
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(json.dumps({
        'event': 'extraction_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        if http_method == 'POST' and '/process' in path:
            return handle_process(event, user_id)
        elif http_method == 'GET' and '/extraction/' in path:
            return handle_get_extraction(event, user_id)
        else:
            return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in extraction handler: {e}")
        return build_error_response(e, 'extraction_handler')


def handle_process(event, user_id):
    """Handle POST /vocab/process - trigger vocabulary extraction.

    Expected body:
    {
        "vocabSetId": "uuid",
        "imageKey": "s3-object-key" (optional, fetched from DB if missing)
    }
    """
    body = parse_body(event)
    vocab_set_id = body.get('vocabSetId')

    if not vocab_set_id:
        return build_response(400, {'error': 'vocabSetId is required'})

    is_valid, err = validate_uuid(vocab_set_id, 'vocabSetId')
    if not is_valid:
        return build_response(400, {'error': err})

    # Verify ownership and get image key
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    response = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )

    item = response.get('Item')
    if not item:
        return build_response(404, {'error': 'Vocabulary set not found'})

    image_key = body.get('imageKey') or item.get('sourceImageKey')
    if not image_key:
        return build_response(400, {'error': 'No image associated with this vocabulary set'})

    # Update status to processing
    vocabsets_table.update_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id},
        UpdateExpression='SET extractionStatus = :status, updatedAt = :ts',
        ExpressionAttributeValues={
            ':status': 'processing',
            ':ts': get_timestamp(),
        }
    )

    # Try Textract first
    vocab_pairs = []
    extraction_method = 'textract'

    try:
        vocab_pairs, confidence = extract_with_textract(image_key)

        # If confidence is low or no pairs found, try OpenAI fallback
        if confidence < 0.7 or not vocab_pairs:
            logger.info(json.dumps({
                'event': 'textract_low_confidence',
                'confidence': confidence,
                'pairsFound': len(vocab_pairs),
                'fallbackToOpenAI': True,
            }))
            openai_pairs = extract_with_openai(image_key)
            if openai_pairs and (not vocab_pairs or len(openai_pairs) > len(vocab_pairs)):
                vocab_pairs = openai_pairs
                extraction_method = 'openai'

    except Exception as e:
        logger.warning(f"Textract failed, trying OpenAI fallback: {e}")
        vocab_pairs = extract_with_openai(image_key)
        extraction_method = 'openai_fallback'

    # Store extracted items
    if vocab_pairs:
        item_count = store_vocab_items(vocab_set_id, vocab_pairs)
        status = 'review'
    else:
        item_count = 0
        status = 'failed'

    # Update VocabSet record - use ADD for itemCount to support multiple pages
    vocabsets_table.update_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id},
        UpdateExpression=(
            'SET extractionStatus = :status, updatedAt = :ts, '
            'extractionMethod = :method '
            'ADD itemCount :count'
        ),
        ExpressionAttributeValues={
            ':status': status,
            ':ts': get_timestamp(),
            ':count': item_count,
            ':method': extraction_method,
        }
    )

    logger.info(json.dumps({
        'event': 'extraction_complete',
        'vocabSetId': vocab_set_id,
        'status': status,
        'itemCount': item_count,
        'method': extraction_method,
    }))

    return build_response(200, {
        'vocabSetId': vocab_set_id,
        'status': status,
        'itemCount': item_count,
        'extractionMethod': extraction_method,
    })


def handle_get_extraction(event, user_id):
    """Handle GET /vocab/extraction/{vocabSetId} - get extraction results."""
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

    # Get extracted items
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    items_response = items_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('vocabSetId').eq(vocab_set_id)
    )

    items = items_response.get('Items', [])
    items.sort(key=lambda x: x.get('order', 0))

    return build_response(200, {
        'vocabSetId': vocab_set_id,
        'status': vocab_set.get('extractionStatus'),
        'itemCount': len(items),
        'items': [
            {
                'itemId': item['itemId'],
                'source': item.get('source', item.get('german', '')),
                'target': item.get('target', item.get('french', '')),
                'notes': item.get('notes', ''),
                'confidence': item.get('confidence', 0),
                'order': item.get('order', 0),
            }
            for item in items
        ],
    })
