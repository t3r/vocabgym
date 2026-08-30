"""Tests for vocab_crud identicon integration:
- image key -> identicon key mapping (must match icon_handler)
- original scans deleted from S3 on approval
"""

import importlib.util
import os

import boto3
import pytest
from moto import mock_aws

import sys
# Shared layer (lib.utils etc.) must be importable by the handler under test.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))

# Clear real/expired session creds so moto intercepts cleanly.
for _k in (
    'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
    'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
):
    os.environ.pop(_k, None)
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'

_VC_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'functions', 'vocab_crud_handler', 'app.py'
)
_ICON_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'functions', 'icon_handler', 'app.py'
)

_ENV = {
    'VOCABSETS_TABLE': 'vc-vocabsets',
    'VOCABITEMS_TABLE': 'vc-vocabitems',
    'PROGRESS_TABLE': 'vc-progress',
    'USERS_TABLE': 'vc-users',
    'LEAGUES_TABLE': 'vc-leagues',
    'IMAGES_BUCKET': 'vc-images',
    'REGION': 'eu-central-1',
}


@pytest.fixture(autouse=True)
def _clean_creds():
    for k in (
        'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
        'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
    ):
        os.environ.pop(k, None)
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
    yield


def _load(path, name, env):
    for k, v in env.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_icon_key_matches_icon_handler():
    """vocab_crud._icon_key_for must produce the SAME keys as icon_handler."""
    vc = _load(_VC_PATH, 'vc_app_iconkey', _ENV)
    icon = _load(_ICON_PATH, 'icon_app_iconkey', {'IMAGES_BUCKET': 'vc-images', 'REGION': 'eu-central-1'})
    src = 'images/user-1/set-abc/1693400000-original.jpg'
    for roboset in ('set1', 'set4'):
        assert vc._icon_key_for(src, roboset) == icon._icon_key(src, roboset)


@mock_aws
def test_approve_deletes_original_scans():
    region = 'eu-central-1'
    import uuid
    set_id = str(uuid.uuid4())
    s3 = boto3.client('s3', region_name=region)
    s3.create_bucket(
        Bucket='vc-images',
        CreateBucketConfiguration={'LocationConstraint': region},
    )
    dynamodb = boto3.resource('dynamodb', region_name=region)
    vocabsets = dynamodb.create_table(
        TableName='vc-vocabsets',
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
    dynamodb.create_table(
        TableName='vc-vocabitems',
        KeySchema=[
            {'AttributeName': 'vocabSetId', 'KeyType': 'HASH'},
            {'AttributeName': 'itemId', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'vocabSetId', 'AttributeType': 'S'},
            {'AttributeName': 'itemId', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )

    # Two original scans (multi-page set) + their identicons in S3
    k1 = f'images/u1/{set_id}/100-original.jpg'
    k2 = f'images/u1/{set_id}/200-original.jpg'
    icon1 = f'identicons/u1/{set_id}/100-set1.png'
    for k in (k1, k2):
        s3.put_object(Bucket='vc-images', Key=k, Body=b'JPEGDATA')
    s3.put_object(Bucket='vc-images', Key=icon1, Body=b'PNGICON')

    vocabsets.put_item(Item={
        'vocabSetId': set_id, 'userId': 'u1', 'title': 'X',
        'sourceImageKey': k1, 'imageKeys': [k1, k2],
        'extractionStatus': 'review', 'itemCount': 0, 'metadata': {},
    })

    vc = _load(_VC_PATH, 'vc_app_approve', _ENV)
    event = {
        'httpMethod': 'PUT',
        'pathParameters': {'vocabSetId': set_id},
        'requestContext': {'authorizer': {'claims': {'sub': 'u1'}}},
        'body': '{"approve": true}',
    }
    resp = vc.lambda_handler(event, None)
    assert resp['statusCode'] == 200

    # Originals gone
    remaining = s3.list_objects_v2(Bucket='vc-images', Prefix='images/').get('Contents', [])
    assert remaining == [], f"originals should be deleted, found {remaining}"
    # Identicon preserved
    icons = s3.list_objects_v2(Bucket='vc-images', Prefix='identicons/').get('Contents', [])
    assert len(icons) == 1 and icons[0]['Key'] == icon1
