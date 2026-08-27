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
bedrock_client = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
ssm_client = boto3.client('ssm')

# Environment variables
IMAGES_BUCKET = os.environ['IMAGES_BUCKET']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
EXTRACTION_PROMPT_PARAM = os.environ.get('EXTRACTION_PROMPT_PARAM', '')
VERIFICATION_PROMPT_PARAM = os.environ.get('VERIFICATION_PROMPT_PARAM', '')

# Prompt cache (loaded once per Lambda container, survives warm starts)
_prompt_cache = {}


def _get_prompt(param_name, fallback=''):
    """Load a prompt template from SSM Parameter Store with caching.

    Prompts are cached for the lifetime of the Lambda container (warm starts).
    To force a reload, update the Lambda environment variable (triggers cold start).

    Args:
        param_name: SSM Parameter name
        fallback: Fallback prompt if SSM read fails

    Returns:
        str: Prompt template text
    """
    if param_name in _prompt_cache:
        return _prompt_cache[param_name]

    if not param_name:
        return fallback

    try:
        response = ssm_client.get_parameter(Name=param_name)
        prompt = response['Parameter']['Value']
        _prompt_cache[param_name] = prompt
        logger.info(f"Loaded prompt from SSM: {param_name}")
        return prompt
    except Exception as e:
        logger.warning(f"Failed to load prompt from SSM ({param_name}): {e}")
        return fallback


def extract_with_textract(image_key):
    """Use AWS Textract to analyze the document for tables.

    Args:
        image_key: S3 object key for the image

    Returns:
        tuple: (vocab_pairs, confidence, raw_text) where vocab_pairs is list of {source, target}
               and raw_text is the full OCR text for LLM fallback
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
    raw_text = parser.extract_raw_text()

    # Calculate average confidence
    if vocab_pairs:
        avg_confidence = sum(p.get('confidence', 0) for p in vocab_pairs) / len(vocab_pairs)
    else:
        avg_confidence = 0.0

    logger.info(json.dumps({
        'event': 'textract_complete',
        'pairsFound': len(vocab_pairs),
        'avgConfidence': round(avg_confidence, 2),
        'rawTextLines': raw_text.count('\n') + 1 if raw_text else 0,
    }))

    return vocab_pairs, avg_confidence, raw_text


def detect_target_language(raw_text):
    """Use Bedrock to detect the target language from raw OCR text.

    Analyzes vocabulary page text to determine if it's French, English,
    Spanish, or Italian alongside German.

    Args:
        raw_text: Raw OCR text from Textract

    Returns:
        str: Language code ('fr', 'en', 'es', 'it') or None if detection fails
    """
    if not raw_text or len(raw_text.strip()) < 30:
        return None

    # Take first 500 chars to save tokens
    sample = raw_text[:500]

    prompt = f"""Analysiere diesen OCR-Text einer Schulbuchseite. Die Seite enthält deutsche Vokabeln und Übersetzungen in EINER Fremdsprache.

Welche Fremdsprache ist es? Antworte NUR mit dem Sprachcode:
- fr (Französisch)
- en (Englisch)
- es (Spanisch)
- it (Italienisch)

Antworte mit GENAU EINEM Sprachcode, nichts anderes.

Text:
{sample}"""

    try:
        response = bedrock_client.converse(
            modelId='eu.amazon.nova-pro-v1:0',
            messages=[{'role': 'user', 'content': [{'text': prompt}]}],
            inferenceConfig={'maxTokens': 10},
        )
        result = response['output']['message']['content'][0]['text'].strip().lower()

        if result in ('fr', 'en', 'es', 'it'):
            logger.info(f"Detected target language: {result}")
            return result

        # Try to extract code from longer response
        for code in ('fr', 'en', 'es', 'it'):
            if code in result:
                logger.info(f"Detected target language (parsed): {code}")
                return code

        logger.warning(f"Could not parse language from: {result}")
        return None

    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return None


def extract_with_bedrock_from_text(raw_text, target_language='fr'):
    """Use Bedrock LLM to extract vocabulary pairs directly from raw OCR text.

    This is used when Textract table detection fails or finds too few pairs,
    e.g. for vocabulary pages that use free-text layouts rather than strict tables.

    Args:
        raw_text: Full OCR text from Textract LINE blocks
        target_language: Target language code

    Returns:
        list: List of {source, target} vocabulary pairs
    """
    if not raw_text or len(raw_text.strip()) < 20:
        return []

    lang_config = get_language(target_language) or get_language(DEFAULT_TARGET_LANGUAGE)
    lang_name_de = lang_config.get('name', 'Französisch') if lang_config else 'Französisch'

    # Load prompt template from SSM Parameter Store (cached per Lambda container)
    prompt_template = _get_prompt(EXTRACTION_PROMPT_PARAM)
    if prompt_template:
        from string import Template
        prompt = Template(prompt_template).safe_substitute(
            lang_name_de=lang_name_de, raw_text=raw_text
        )
    else:
        # Inline fallback if SSM is unavailable
        prompt = f"""Du bekommst den OCR-Text einer Schulbuchseite. Extrahiere ALLE Vokabelpaare (Deutsch ↔ {lang_name_de}).
Antworte NUR mit einem JSON-Array: [{{"source": "deutsch", "target": "{lang_name_de} Wort"}}]
OCR-Text:
{raw_text}"""

    try:
        response = bedrock_client.converse(
            modelId='eu.amazon.nova-pro-v1:0',
            messages=[
                {'role': 'user', 'content': [{'text': prompt}]}
            ],
            inferenceConfig={
                'maxTokens': 4096,
            }
        )

        result_text = response['output']['message']['content'][0]['text'].strip()

        # Parse JSON response (handle markdown code blocks)
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1]
            result_text = result_text.rsplit('```', 1)[0]
        result_text = result_text.strip()

        vocab_pairs = json.loads(result_text)

        if isinstance(vocab_pairs, list):
            # Add confidence score
            for pair in vocab_pairs:
                pair['confidence'] = 0.90

            logger.info(json.dumps({
                'event': 'bedrock_extraction_complete',
                'pairsFound': len(vocab_pairs),
            }))
            return vocab_pairs
        else:
            logger.warning("Bedrock extraction returned non-list result")
            return []

    except Exception as e:
        logger.exception(f"Bedrock extraction from text failed: {e}")
        return []


def verify_with_bedrock(vocab_pairs, target_language='fr'):
    """Use Amazon Bedrock (Claude) to verify and clean extracted vocabulary pairs.

    Removes non-vocabulary entries (headers, instructions, page numbers),
    formats multiple meanings with semicolons, and cleans up noise.

    Args:
        vocab_pairs: List of {source, target} dicts from Textract
        target_language: Target language code for context

    Returns:
        list: Cleaned list of {source, target} dicts
    """
    if not vocab_pairs:
        return vocab_pairs

    lang_config = get_language(target_language) or get_language(DEFAULT_TARGET_LANGUAGE)
    lang_name = lang_config['nameEnglish'] if lang_config else 'French'

    # Build the pairs as text for the prompt
    pairs_text = '\n'.join(
        f"{i+1}. {p.get('source', '')} | {p.get('target', '')}"
        for i, p in enumerate(vocab_pairs)
    )

    # Load prompt template from SSM Parameter Store (cached per Lambda container)
    prompt_template = _get_prompt(VERIFICATION_PROMPT_PARAM)
    if prompt_template:
        from string import Template
        prompt = Template(prompt_template).safe_substitute(
            lang_name=lang_name, pairs_text=pairs_text
        )
    else:
        # Inline fallback if SSM is unavailable
        prompt = f"""Extrahiere echte Vokabelpaare (Deutsch ↔ {lang_name}) aus dieser Liste.
Antworte NUR mit JSON-Array: [{{"source": "deutsch", "target": "übersetzung"}}]
Paare:
{pairs_text}"""

    try:
        response = bedrock_client.converse(
            modelId='eu.amazon.nova-pro-v1:0',
            messages=[
                {'role': 'user', 'content': [{'text': prompt}]}
            ],
            inferenceConfig={
                'maxTokens': 4096,
            }
        )

        result_text = response['output']['message']['content'][0]['text'].strip()

        # Parse JSON response
        # Handle potential markdown code blocks
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1]
            result_text = result_text.rsplit('```', 1)[0]
        result_text = result_text.strip()

        verified_pairs = json.loads(result_text)

        if isinstance(verified_pairs, list) and len(verified_pairs) > 0:
            logger.info(json.dumps({
                'event': 'bedrock_verification_complete',
                'inputPairs': len(vocab_pairs),
                'outputPairs': len(verified_pairs),
                'removed': len(vocab_pairs) - len(verified_pairs),
            }))
            return verified_pairs
        else:
            logger.warning("Bedrock returned empty or invalid result, using original pairs")
            return vocab_pairs

    except Exception as e:
        logger.warning(f"Bedrock verification failed, using original pairs: {e}")
        return vocab_pairs


def store_vocab_items(vocab_set_id, vocab_pairs, image_key=None):
    """Store extracted vocabulary items in DynamoDB.

    Args:
        vocab_set_id: The vocabulary set ID
        vocab_pairs: List of {source, target, confidence} dicts
        image_key: S3 key of the source image for these items

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
            item_data = {
                'vocabSetId': vocab_set_id,
                'itemId': item_id,
                'source': source_text,
                'target': target_text,
                'notes': pair.get('notes', ''),
                'order': i + 1,
                'confidence': int(pair.get('confidence', 0) * 100),
                'createdAt': timestamp,
                'updatedAt': timestamp,
                'isActive': True,
            }
            if image_key:
                item_data['imageKey'] = image_key
            batch.put_item(Item=item_data)

    return len(vocab_pairs)



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

    # Try Textract first for OCR, then use Bedrock for intelligent extraction
    vocab_pairs = []
    raw_text = ''
    extraction_method = 'textract'
    target_language = item.get('targetLanguage', '')

    try:
        vocab_pairs, confidence, raw_text = extract_with_textract(image_key)

        # Always prefer Bedrock extraction from raw text when raw text is available.
        # Textract table parsing often misaligns columns on complex workbook layouts,
        # while the LLM can intelligently parse the full OCR text regardless of layout.
        if raw_text and len(raw_text.strip()) > 50:
            # Auto-detect language if not set on the VocabSet
            if not target_language:
                target_language = detect_target_language(raw_text) or DEFAULT_TARGET_LANGUAGE
                # Save detected language back to the VocabSet
                vocabsets_table.update_item(
                    Key={'vocabSetId': vocab_set_id, 'userId': user_id},
                    UpdateExpression='SET targetLanguage = :lang',
                    ExpressionAttributeValues={':lang': target_language},
                )
                logger.info(json.dumps({
                    'event': 'language_auto_detected',
                    'vocabSetId': vocab_set_id,
                    'detectedLanguage': target_language,
                }))

            bedrock_pairs = extract_with_bedrock_from_text(raw_text, target_language)

            if bedrock_pairs and len(bedrock_pairs) >= len(vocab_pairs):
                logger.info(json.dumps({
                    'event': 'using_bedrock_extraction',
                    'textractPairs': len(vocab_pairs),
                    'bedrockPairs': len(bedrock_pairs),
                    'rawTextLength': len(raw_text),
                }))
                vocab_pairs = bedrock_pairs
                extraction_method = 'bedrock_from_text'
            else:
                logger.info(json.dumps({
                    'event': 'keeping_textract_pairs',
                    'textractPairs': len(vocab_pairs),
                    'bedrockPairs': len(bedrock_pairs) if bedrock_pairs else 0,
                }))

    except Exception as e:
        logger.warning(f"Textract failed: {e}")
        # If textract completely fails, there's no raw_text either
        extraction_method = 'failed'

    # Store extracted items
    if vocab_pairs:
        if not target_language:
            target_language = DEFAULT_TARGET_LANGUAGE

        # Only verify with Bedrock if extraction came from Textract table parsing
        # (Bedrock extraction already produces clean pairs)
        if extraction_method == 'textract':
            vocab_pairs = verify_with_bedrock(vocab_pairs, target_language)

        if vocab_pairs:
            item_count = store_vocab_items(vocab_set_id, vocab_pairs, image_key=image_key)
            status = 'review'
        else:
            item_count = 0
            status = 'review'  # Still reviewable, just no valid pairs found
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
