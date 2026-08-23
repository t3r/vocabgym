"""Common utilities for VocabTrainer Lambda functions."""

import json
import uuid
import time
import logging
import traceback
from decimal import Decimal

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def build_response(status_code, body=None, headers=None):
    """Build a standard API Gateway response with CORS headers.

    Args:
        status_code: HTTP status code
        body: Response body (will be JSON-serialized)
        headers: Additional headers to include

    Returns:
        dict: API Gateway response format
    """
    response_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
    }

    if headers:
        response_headers.update(headers)

    response = {
        'statusCode': status_code,
        'headers': response_headers,
    }

    if body is not None:
        response['body'] = json.dumps(body, cls=DecimalEncoder)

    return response


def build_error_response(error, context=None):
    """Build a 500 error response with a unique error ID for tracking.

    Logs the full exception with the error ID so it can be correlated
    with user reports.

    Args:
        error: The exception that occurred
        context: Optional context string (e.g., 'practice_handler.handle_complete')

    Returns:
        dict: API Gateway error response with errorId
    """
    error_id = str(uuid.uuid4())[:8]
    error_msg = str(error)
    tb = traceback.format_exc()

    logger.error(json.dumps({
        'event': 'unhandled_error',
        'errorId': error_id,
        'context': context or 'unknown',
        'error': error_msg,
        'errorType': type(error).__name__,
        'traceback': tb,
    }))

    return build_response(500, {
        'error': 'Ein interner Fehler ist aufgetreten.',
        'errorId': error_id,
        'message': f'Bitte melde diesen Fehler mit der ID: {error_id}',
    })


def get_user_id_from_event(event):
    """Extract the userId (Cognito sub) from the API Gateway event.

    Args:
        event: API Gateway Lambda proxy event

    Returns:
        str: The userId from Cognito claims

    Raises:
        ValueError: If userId cannot be extracted
    """
    try:
        claims = event['requestContext']['authorizer']['claims']
        user_id = claims['sub']
        if not user_id:
            raise ValueError("Empty userId in claims")
        return user_id
    except (KeyError, TypeError) as e:
        logger.error(f"Failed to extract userId from event: {e}")
        raise ValueError(f"Unable to extract userId from authorization context: {e}")


def generate_uuid():
    """Generate a new UUID4 string.

    Returns:
        str: A new UUID string
    """
    return str(uuid.uuid4())


def get_timestamp():
    """Get current Unix timestamp as integer.

    Returns:
        int: Current Unix timestamp
    """
    return int(time.time())


def parse_body(event):
    """Parse the JSON body from an API Gateway event.

    Args:
        event: API Gateway Lambda proxy event

    Returns:
        dict: Parsed JSON body

    Raises:
        ValueError: If body is missing or invalid JSON
    """
    body = event.get('body')
    if not body:
        raise ValueError("Request body is required")

    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in request body: {e}")

    return body


def get_path_parameter(event, param_name):
    """Extract a path parameter from the event.

    Args:
        event: API Gateway Lambda proxy event
        param_name: Name of the path parameter

    Returns:
        str: The path parameter value

    Raises:
        ValueError: If the parameter is missing
    """
    params = event.get('pathParameters') or {}
    value = params.get(param_name)
    if not value:
        raise ValueError(f"Missing required path parameter: {param_name}")
    return value


def get_query_parameter(event, param_name, default=None):
    """Extract a query string parameter from the event.

    Args:
        event: API Gateway Lambda proxy event
        param_name: Name of the query parameter
        default: Default value if parameter is missing

    Returns:
        str: The query parameter value or default
    """
    params = event.get('queryStringParameters') or {}
    return params.get(param_name, default)
