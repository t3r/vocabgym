"""Tests for the upload handler Lambda function."""

import json
import os
import sys
import pytest

import boto3
from moto import mock_aws

# Add function and layer to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'functions', 'upload_handler'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))


# Set environment variables before importing handler
os.environ['IMAGES_BUCKET'] = 'test-images-bucket'
os.environ['VOCABSETS_TABLE'] = 'test-vocabsets-table'
os.environ['VOCABITEMS_TABLE'] = 'test-vocabitems-table'
os.environ['USERS_TABLE'] = 'test-users-table'


def _load_upload_app():
    """Load the upload handler by explicit file path under a unique module name.

    Using a bare `import app` collides with other handlers' `app.py` modules in
    the full test suite (shared `sys.modules['app']`), which made these tests
    order-dependent. Loading by path makes them isolated and robust.
    """
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), '..', 'functions', 'upload_handler', 'app.py')
    spec = importlib.util.spec_from_file_location('upload_app_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
os.environ['SESSIONS_TABLE'] = 'test-sessions-table'
os.environ['PROGRESS_TABLE'] = 'test-progress-table'
os.environ['REGION'] = 'eu-central-1'
os.environ['ENVIRONMENT'] = 'test'
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'


def create_api_gateway_event(body=None, path_params=None, method='POST', user_id='test-user-123'):
    """Helper to create a mock API Gateway event."""
    event = {
        'httpMethod': method,
        'path': '/vocab/upload',
        'pathParameters': path_params or {},
        'queryStringParameters': {},
        'headers': {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-token',
        },
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': user_id,
                    'email': 'test@example.com',
                }
            }
        },
        'body': json.dumps(body) if body else None,
    }
    return event


@pytest.fixture
def aws_resources():
    """Create mock AWS resources for testing."""
    with mock_aws():
        # Create mock S3 bucket
        s3 = boto3.client('s3', region_name='eu-central-1')
        s3.create_bucket(
            Bucket='test-images-bucket',
            CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'}
        )

        # Create mock DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
        table = dynamodb.create_table(
            TableName='test-vocabsets-table',
            KeySchema=[
                {'AttributeName': 'vocabSetId', 'KeyType': 'HASH'},
                {'AttributeName': 'userId', 'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'vocabSetId', 'AttributeType': 'S'},
                {'AttributeName': 'userId', 'AttributeType': 'S'},
            ],
            BillingMode='PAY_PER_REQUEST',
        )

        # Users table — upload_handler maintains a race-safe owned-set counter here.
        dynamodb.create_table(
            TableName='test-users-table',
            KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST',
        )

        yield {'s3': s3, 'dynamodb': dynamodb, 'table': table}


def test_successful_upload_request(aws_resources):
    """Test a successful upload request generates presigned URL."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'workbook_page.jpg',
            'contentType': 'image/jpeg',
        }
    )

    response = app.lambda_handler(event, None)

    assert response['statusCode'] == 200

    body = json.loads(response['body'])
    assert 'vocabSetId' in body
    assert 'uploadUrl' in body
    assert 'imageKey' in body
    assert body['expiresIn'] == 300
    assert 'test-user-123' in body['imageKey']


def test_upload_multidot_filename_forces_safe_extension(aws_resources):
    """A crafted name like 'evil.jpg.exe' must not place '.exe' in the S3 key.

    The content type is valid image/jpeg, so the upload proceeds, but the key
    extension must be whitelisted (falls back to jpg for anything not in
    {jpg,jpeg,png})."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'evil.jpg.exe',
            'contentType': 'image/jpeg',
        }
    )
    response = app.lambda_handler(event, None)

    # validate_file_upload rejects the '.exe' extension outright (defense #1).
    # If it ever passed, the key must still not end in .exe (defense #2).
    if response['statusCode'] == 200:
        body = json.loads(response['body'])
        assert body['imageKey'].endswith('.jpg')
        assert '.exe' not in body['imageKey']
    else:
        assert response['statusCode'] == 400


def test_upload_png_keeps_png_extension(aws_resources):
    """A legitimate .png keeps its extension in the key."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'seite.png',
            'contentType': 'image/png',
        }
    )
    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['imageKey'].endswith('.png')


def test_upload_missing_file_name(aws_resources):
    """Test upload request without fileName returns 400."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'contentType': 'image/jpeg',
        }
    )

    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 400


def test_upload_invalid_content_type(aws_resources):
    """Test upload with invalid content type returns 400."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'document.pdf',
            'contentType': 'application/pdf',
        }
    )

    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 400

    body = json.loads(response['body'])
    assert 'Unsupported file type' in body['error']


def test_upload_missing_body(aws_resources):
    """Test upload request without body returns 400."""
    app = _load_upload_app()

    event = create_api_gateway_event(body=None)
    event['body'] = None

    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 400


def test_upload_creates_dynamodb_record(aws_resources):
    """Test that upload creates initial VocabSet record in DynamoDB."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'page1.png',
            'contentType': 'image/png',
        }
    )

    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 200

    body = json.loads(response['body'])
    vocab_set_id = body['vocabSetId']

    # Verify DynamoDB record was created
    table = aws_resources['dynamodb'].Table('test-vocabsets-table')
    db_response = table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': 'test-user-123'}
    )

    item = db_response.get('Item')
    assert item is not None
    assert item['extractionStatus'] == 'pending'
    assert item['sourceImageKey'] == body['imageKey']


def test_upload_cors_headers(aws_resources):
    """Test that response includes CORS headers."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'test.jpg',
            'contentType': 'image/jpeg',
        }
    )

    response = app.lambda_handler(event, None)

    assert 'Access-Control-Allow-Origin' in response['headers']
    assert 'Access-Control-Allow-Methods' in response['headers']


def test_upload_no_auth(aws_resources):
    """Test that request without auth returns 400."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'test.jpg',
            'contentType': 'image/jpeg',
        }
    )
    # Remove authorizer claims
    event['requestContext'] = {}

    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 400


def test_upload_defaults_source_language_to_de(aws_resources):
    """A new set without sourceLanguage stores 'de' (German default)."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={'fileName': 'p.jpg', 'contentType': 'image/jpeg'}
    )
    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 200
    vocab_set_id = json.loads(response['body'])['vocabSetId']

    table = aws_resources['dynamodb'].Table('test-vocabsets-table')
    item = table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': 'test-user-123'}
    )['Item']
    assert item['sourceLanguage'] == 'de'


def test_upload_stores_explicit_source_language(aws_resources):
    """An explicit supported pair (de->fr) is stored."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'p.jpg', 'contentType': 'image/jpeg',
            'sourceLanguage': 'de', 'targetLanguage': 'fr',
        }
    )
    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 200
    vocab_set_id = json.loads(response['body'])['vocabSetId']

    table = aws_resources['dynamodb'].Table('test-vocabsets-table')
    item = table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': 'test-user-123'}
    )['Item']
    assert item['sourceLanguage'] == 'de'
    assert item['targetLanguage'] == 'fr'


def test_upload_rejects_unsupported_pair(aws_resources):
    """An unsupported source->target pair (e.g. fr->de, not curated) → 400."""
    app = _load_upload_app()

    event = create_api_gateway_event(
        body={
            'fileName': 'p.jpg', 'contentType': 'image/jpeg',
            'sourceLanguage': 'fr', 'targetLanguage': 'de',
        }
    )
    response = app.lambda_handler(event, None)
    assert response['statusCode'] == 400
    assert 'nicht unterstützt' in json.loads(response['body'])['error']
