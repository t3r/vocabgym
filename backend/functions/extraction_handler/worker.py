"""Async extraction worker.

Consumes SQS messages (one per image) enqueued by extraction_handler's
POST /vocab/process, runs the Textract + Bedrock extraction for that single
image, and atomically records the page result on the vocab set. When all pages
of a set are done, the set is finalised to 'review' (or 'failed' if every page
failed).

Idempotency: SQS is at-least-once, so a message may be delivered more than once.
We guard by recording processed image keys on the set (processedPages set) and
skipping a page that was already counted, so the counters stay correct.
"""

import json
import logging
import os

import boto3

import app  # shared extraction logic (process_single_image, record_page_result)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']


def _claim_page(vocab_set_id, user_id, image_key):
    """Atomically claim an image for processing (idempotency guard).

    Adds the image key to the set's processedPages string-set only if it is not
    already present. Returns True if we won the claim (should process), False if
    the page was already processed (duplicate delivery → skip).
    """
    table = dynamodb.Table(VOCABSETS_TABLE)
    try:
        table.update_item(
            Key={'vocabSetId': vocab_set_id, 'userId': user_id},
            UpdateExpression='ADD processedPages :k',
            ConditionExpression='attribute_not_exists(processedPages) OR NOT contains(processedPages, :kv)',
            ExpressionAttributeValues={
                ':k': {image_key},        # string set
                ':kv': image_key,
            },
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.info(json.dumps({
            'event': 'duplicate_page_skipped',
            'vocabSetId': vocab_set_id,
            'imageKey': image_key,
        }))
        return False


def lambda_handler(event, context):
    """SQS event handler. BatchSize is 1, but handle multiple records defensively.

    A raised exception makes SQS retry the message (up to maxReceiveCount, then
    DLQ). We only raise for unexpected/transient errors; a normal extraction
    failure is recorded as a failed page (no retry needed).
    """
    for record in event.get('Records', []):
        try:
            msg = json.loads(record['body'])
        except (ValueError, KeyError) as e:
            logger.error(f"Malformed SQS message, dropping: {e}")
            continue  # don't retry un-parseable messages

        vocab_set_id = msg.get('vocabSetId')
        user_id = msg.get('userId')
        image_key = msg.get('imageKey')
        target_language = msg.get('targetLanguage', '')

        if not (vocab_set_id and user_id and image_key):
            logger.error(json.dumps({'event': 'incomplete_message', 'body': msg}))
            continue

        # Idempotency: skip if this page was already processed.
        if not _claim_page(vocab_set_id, user_id, image_key):
            continue

        page_ok, item_count = app.process_single_image(
            vocab_set_id, user_id, image_key, target_language
        )
        app.record_page_result(vocab_set_id, user_id, page_ok)

    return {'statusCode': 200}
