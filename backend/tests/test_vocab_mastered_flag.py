"""Tests for the 'mastered' flag on GET /vocab list entries.

'mastered' mirrors practice_handler._set_mastery_state (every item at
masteryLevel >= 4) and drives the Sammlung (collection) view, which shows the
sets the user has fully learned. Pins both the positive and negative case.
"""

import importlib.util
import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))

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

_ENV = {
    'VOCABSETS_TABLE': 'vm-vocabsets',
    'VOCABITEMS_TABLE': 'vm-vocabitems',
    'PROGRESS_TABLE': 'vm-progress',
    'USERS_TABLE': 'vm-users',
    'LEAGUES_TABLE': 'vm-leagues',
    'IMAGES_BUCKET': 'vm-images',
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


def _load():
    for k, v in _ENV.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location('vc_app_mastered', _VC_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tables(dynamodb):
    dynamodb.create_table(
        TableName='vm-vocabsets',
        KeySchema=[
            {'AttributeName': 'vocabSetId', 'KeyType': 'HASH'},
            {'AttributeName': 'userId', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'vocabSetId', 'AttributeType': 'S'},
            {'AttributeName': 'userId', 'AttributeType': 'S'},
            {'AttributeName': 'createdAt', 'AttributeType': 'N'},
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'userId-createdAt-index',
            'KeySchema': [
                {'AttributeName': 'userId', 'KeyType': 'HASH'},
                {'AttributeName': 'createdAt', 'KeyType': 'RANGE'},
            ],
            'Projection': {'ProjectionType': 'ALL'},
        }],
        BillingMode='PAY_PER_REQUEST',
    )
    dynamodb.create_table(
        TableName='vm-progress',
        KeySchema=[
            {'AttributeName': 'progressKey', 'KeyType': 'HASH'},
            {'AttributeName': 'itemId', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'progressKey', 'AttributeType': 'S'},
            {'AttributeName': 'itemId', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    dynamodb.create_table(
        TableName='vm-users',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )


def _list_event(user_id='u1'):
    return {
        'httpMethod': 'GET',
        'path': '/vocab',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
    }


def _put_set(dynamodb, set_id, user_id, item_count, created):
    dynamodb.Table('vm-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': user_id, 'title': 'S',
        'extractionStatus': 'approved', 'itemCount': item_count,
        'createdAt': created, 'metadata': {},
        'sourceImageKey': f'images/{user_id}/{set_id}/1-original.jpg',
        'imageKeys': [f'images/{user_id}/{set_id}/1-original.jpg'],
    })


def _put_progress(dynamodb, user_id, set_id, item_id, level):
    dynamodb.Table('vm-progress').put_item(Item={
        'progressKey': f'{user_id}#{set_id}', 'itemId': item_id,
        'masteryLevel': level, 'correctCount': 5, 'incorrectCount': 0,
        'lastPracticedAt': 1000,
    })


def _find(sets, set_id):
    return next(s for s in sets if s['vocabSetId'] == set_id)


@mock_aws
def test_set_is_mastered_when_all_items_level_ge_4():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(Bucket='vm-images',
                     CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'})
    _tables(dynamodb)

    _put_set(dynamodb, 'set-mastered', 'u1', item_count=2, created=200)
    _put_progress(dynamodb, 'u1', 'set-mastered', 'i1', 4)
    _put_progress(dynamodb, 'u1', 'set-mastered', 'i2', 5)

    app = _load()
    resp = app.lambda_handler(_list_event('u1'), None)
    assert resp['statusCode'] == 200
    sets = json.loads(resp['body'])['vocabSets']
    assert _find(sets, 'set-mastered')['mastered'] is True


@mock_aws
def test_set_not_mastered_when_one_item_below_threshold():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(Bucket='vm-images',
                     CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'})
    _tables(dynamodb)

    # 3 items, only 2 reach level 4 -> not fully mastered
    _put_set(dynamodb, 'set-partial', 'u1', item_count=3, created=100)
    _put_progress(dynamodb, 'u1', 'set-partial', 'i1', 5)
    _put_progress(dynamodb, 'u1', 'set-partial', 'i2', 4)
    _put_progress(dynamodb, 'u1', 'set-partial', 'i3', 2)

    app = _load()
    resp = app.lambda_handler(_list_event('u1'), None)
    sets = json.loads(resp['body'])['vocabSets']
    assert _find(sets, 'set-partial')['mastered'] is False


@mock_aws
def test_unpracticed_set_is_not_mastered():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(Bucket='vm-images',
                     CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'})
    _tables(dynamodb)

    _put_set(dynamodb, 'set-new', 'u1', item_count=5, created=50)  # no progress at all

    app = _load()
    resp = app.lambda_handler(_list_event('u1'), None)
    sets = json.loads(resp['body'])['vocabSets']
    assert _find(sets, 'set-new')['mastered'] is False
