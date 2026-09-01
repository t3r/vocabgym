"""Tests for the image_handler (AI comic thumbnails) — API + async worker.

Covers the paths that matter for correctness and cost:
- Cache hit → 200 with a URL and NO enqueue (no generation, no rate-limit spend).
- Cache miss → 202 pending + exactly one SQS job enqueued.
- Owner-or-league access → uniform 404 for a foreign set (no info disclosure).
- Rate limit → 429 once the per-user daily cap is exceeded (misses only).
- Worker pipeline: Nova Pro prompt → Stable Image Core PNG → S3 put; idempotent
  (skips generation when the object already exists).

Bedrock is mocked — tests never make real model calls.
"""

import importlib.util
import json
import os
import sys
from unittest import mock

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))

_IMAGE_DIR = os.path.join(os.path.dirname(__file__), '..', 'functions', 'image_handler')
_APP_PATH = os.path.join(_IMAGE_DIR, 'app.py')
_WORKER_PATH = os.path.join(_IMAGE_DIR, 'worker.py')

_ENV = {
    'IMAGES_BUCKET': 'img-bucket',
    'VOCABSETS_TABLE': 'img-vocabsets',
    'VOCABITEMS_TABLE': 'img-vocabitems',
    'USERS_TABLE': 'img-users',
    'LEAGUES_TABLE': 'img-leagues',
    'THUMBNAIL_USAGE_TABLE': 'img-thumb-usage',
    'THUMBNAIL_QUEUE_URL': '',  # set per-test after the queue is created
    'REGION': 'eu-central-1',
}


def _reset_moto_creds():
    for _k in (
        'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
        'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
    ):
        os.environ.pop(_k, None)
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'


@pytest.fixture(autouse=True)
def _creds():
    _reset_moto_creds()
    yield


def _load(path, name, env):
    for k, v in env.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_infra(env):
    """Create S3 bucket, DynamoDB tables and an SQS queue; return (ddb, queue_url)."""
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(
        Bucket=env['IMAGES_BUCKET'],
        CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'},
    )
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    ddb.create_table(
        TableName=env['VOCABSETS_TABLE'],
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
    ddb.create_table(
        TableName=env['VOCABITEMS_TABLE'],
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
    ddb.create_table(
        TableName=env['USERS_TABLE'],
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName=env['LEAGUES_TABLE'],
        KeySchema=[{'AttributeName': 'leagueId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'leagueId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName=env['THUMBNAIL_USAGE_TABLE'],
        KeySchema=[
            {'AttributeName': 'userId', 'KeyType': 'HASH'},
            {'AttributeName': 'windowStart', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'userId', 'AttributeType': 'S'},
            {'AttributeName': 'windowStart', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    sqs = boto3.client('sqs', region_name='eu-central-1')
    queue_url = sqs.create_queue(QueueName='img-thumb-queue')['QueueUrl']
    return ddb, queue_url, sqs


def _seed_owned_set(ddb, set_id='set-1', user_id='u1', lang='it',
                    item_id='i1', source='das Bad', target='il bagno'):
    ddb.Table('img-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': user_id, 'title': 'Set',
        'targetLanguage': lang, 'extractionStatus': 'approved',
    })
    ddb.Table('img-vocabitems').put_item(Item={
        'vocabSetId': set_id, 'itemId': item_id,
        'source': source, 'target': target, 'isActive': True,
    })


def _post_event(user_id, vocab_set_id, item_id):
    return {
        'httpMethod': 'POST',
        'path': '/images/thumbnail',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
        'body': json.dumps({'vocabSetId': vocab_set_id, 'itemId': item_id}),
    }


def _get_event(user_id, vocab_set_id, item_id):
    return {
        'httpMethod': 'GET',
        'path': f'/images/thumbnail/{vocab_set_id}/{item_id}',
        'pathParameters': {'vocabSetId': vocab_set_id, 'itemId': item_id},
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
    }


def _queue_depth(sqs, queue_url):
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=['ApproximateNumberOfMessages']
    )
    return int(attrs['Attributes']['ApproximateNumberOfMessages'])


# --- API: cache miss enqueues -------------------------------------------

@mock_aws
def test_cache_miss_enqueues_and_returns_202():
    ddb, queue_url, sqs = _make_infra(_ENV)
    _seed_owned_set(ddb)
    env = {**_ENV, 'THUMBNAIL_QUEUE_URL': queue_url}
    app = _load(_APP_PATH, 'img_app_miss', env)

    resp = app.lambda_handler(_post_event('u1', 'set-1', 'i1'), None)
    assert resp['statusCode'] == 202
    assert json.loads(resp['body'])['status'] == 'pending'
    assert _queue_depth(sqs, queue_url) == 1


# --- API: cache hit, no enqueue -----------------------------------------

@mock_aws
def test_cache_hit_returns_url_without_enqueue():
    ddb, queue_url, sqs = _make_infra(_ENV)
    _seed_owned_set(ddb)
    env = {**_ENV, 'THUMBNAIL_QUEUE_URL': queue_url}
    app = _load(_APP_PATH, 'img_app_hit', env)

    # Pre-populate the cache at the exact key the handler computes.
    s3_key = app.thumbnail_s3_key('das Bad', 'il bagno', 'it')
    boto3.client('s3', region_name='eu-central-1').put_object(
        Bucket=env['IMAGES_BUCKET'], Key=s3_key, Body=b'PNGDATA', ContentType='image/png'
    )

    resp = app.lambda_handler(_post_event('u1', 'set-1', 'i1'), None)
    assert resp['statusCode'] == 200
    body = json.loads(resp['body'])
    assert body['status'] == 'ready'
    assert 'url' in body
    # No generation job was enqueued for a cache hit.
    assert _queue_depth(sqs, queue_url) == 0


# --- API: GET poll ------------------------------------------------------

@mock_aws
def test_get_pending_then_ready():
    ddb, queue_url, sqs = _make_infra(_ENV)
    _seed_owned_set(ddb)
    env = {**_ENV, 'THUMBNAIL_QUEUE_URL': queue_url}
    app = _load(_APP_PATH, 'img_app_get', env)

    # Not generated yet → pending.
    resp = app.lambda_handler(_get_event('u1', 'set-1', 'i1'), None)
    assert json.loads(resp['body'])['status'] == 'pending'

    # After the worker cached it → ready.
    s3_key = app.thumbnail_s3_key('das Bad', 'il bagno', 'it')
    boto3.client('s3', region_name='eu-central-1').put_object(
        Bucket=env['IMAGES_BUCKET'], Key=s3_key, Body=b'PNGDATA', ContentType='image/png'
    )
    resp = app.lambda_handler(_get_event('u1', 'set-1', 'i1'), None)
    body = json.loads(resp['body'])
    assert body['status'] == 'ready'
    assert 'url' in body


# --- API: foreign set → uniform 404 -------------------------------------

@mock_aws
def test_foreign_set_returns_404():
    ddb, queue_url, sqs = _make_infra(_ENV)
    _seed_owned_set(ddb, user_id='owner')  # owned by someone else
    env = {**_ENV, 'THUMBNAIL_QUEUE_URL': queue_url}
    app = _load(_APP_PATH, 'img_app_foreign', env)

    # user 'stranger' has no league → no access.
    ddb.Table('img-users').put_item(Item={'userId': 'stranger'})
    resp = app.lambda_handler(_post_event('stranger', 'set-1', 'i1'), None)
    assert resp['statusCode'] == 404
    assert _queue_depth(sqs, queue_url) == 0


# --- API: league member CAN access --------------------------------------

@mock_aws
def test_league_member_can_request():
    ddb, queue_url, sqs = _make_infra(_ENV)
    _seed_owned_set(ddb, user_id='teacher')
    ddb.Table('img-users').put_item(Item={'userId': 'student', 'leagueId': 'lg-1'})
    ddb.Table('img-leagues').put_item(Item={
        'leagueId': 'lg-1', 'teacherUserId': 'teacher', 'vocabSetIds': ['set-1'],
    })
    env = {**_ENV, 'THUMBNAIL_QUEUE_URL': queue_url}
    app = _load(_APP_PATH, 'img_app_league', env)

    resp = app.lambda_handler(_post_event('student', 'set-1', 'i1'), None)
    assert resp['statusCode'] == 202
    assert _queue_depth(sqs, queue_url) == 1


# --- API: rate limit → 429 ----------------------------------------------

@mock_aws
def test_rate_limit_returns_429():
    ddb, queue_url, sqs = _make_infra(_ENV)
    _seed_owned_set(ddb)
    # Cap at 2 generations/day for the test.
    env = {**_ENV, 'THUMBNAIL_QUEUE_URL': queue_url, 'THUMBNAIL_LIMIT_PER_DAY': '2'}
    app = _load(_APP_PATH, 'img_app_rl', env)

    # Distinct items so each is a cache miss (rate limit counts misses).
    for idx in range(2):
        ddb.Table('img-vocabitems').put_item(Item={
            'vocabSetId': 'set-1', 'itemId': f'x{idx}',
            'source': f'wort{idx}', 'target': f'parola{idx}', 'isActive': True,
        })
        r = app.lambda_handler(_post_event('u1', 'set-1', f'x{idx}'), None)
        assert r['statusCode'] == 202

    # Third miss exceeds the cap.
    ddb.Table('img-vocabitems').put_item(Item={
        'vocabSetId': 'set-1', 'itemId': 'x2',
        'source': 'wort2', 'target': 'parola2', 'isActive': True,
    })
    r = app.lambda_handler(_post_event('u1', 'set-1', 'x2'), None)
    assert r['statusCode'] == 429


# --- Worker: two-stage pipeline + idempotency ---------------------------

@mock_aws
def test_worker_generates_and_caches_png():
    _make_infra(_ENV)
    worker = _load(_WORKER_PATH, 'img_worker_gen', _ENV)

    s3_key = 'thumbnails/it/abc123.png'
    msg = {'source': 'das Bad', 'target': 'il bagno', 'lang': 'it', 's3Key': s3_key}
    record = {'Records': [{'body': json.dumps(msg)}]}

    fake_png = b'\x89PNG\r\n\x1a\nFAKE'
    with mock.patch.object(worker, '_build_image_prompt', return_value='comic style bathroom') as m_prompt, \
         mock.patch.object(worker, '_generate_image_png', return_value=fake_png) as m_img:
        worker.lambda_handler(record, None)

    m_prompt.assert_called_once()
    m_img.assert_called_once_with('comic style bathroom')
    obj = boto3.client('s3', region_name='eu-central-1').get_object(
        Bucket=_ENV['IMAGES_BUCKET'], Key=s3_key
    )
    assert obj['Body'].read() == fake_png
    assert obj['ContentType'] == 'image/png'


@mock_aws
def test_worker_idempotent_skips_when_cached():
    _make_infra(_ENV)
    worker = _load(_WORKER_PATH, 'img_worker_idem', _ENV)

    s3_key = 'thumbnails/it/already.png'
    boto3.client('s3', region_name='eu-central-1').put_object(
        Bucket=_ENV['IMAGES_BUCKET'], Key=s3_key, Body=b'EXISTING', ContentType='image/png'
    )
    msg = {'source': 'das Bad', 'target': 'il bagno', 'lang': 'it', 's3Key': s3_key}
    record = {'Records': [{'body': json.dumps(msg)}]}

    with mock.patch.object(worker, '_generate_image_png') as m_img:
        worker.lambda_handler(record, None)
        m_img.assert_not_called()  # already cached → no generation

    # Existing object untouched.
    obj = boto3.client('s3', region_name='eu-central-1').get_object(
        Bucket=_ENV['IMAGES_BUCKET'], Key=s3_key
    )
    assert obj['Body'].read() == b'EXISTING'


@mock_aws
def test_worker_raises_on_generation_failure_for_retry():
    _make_infra(_ENV)
    worker = _load(_WORKER_PATH, 'img_worker_fail', _ENV)

    msg = {'source': 'x', 'target': 'y', 'lang': 'it', 's3Key': 'thumbnails/it/fail.png'}
    record = {'Records': [{'body': json.dumps(msg)}]}

    with mock.patch.object(worker, '_build_image_prompt', return_value='comic style x'), \
         mock.patch.object(worker, '_generate_image_png', return_value=None):
        # Image generation failed → raise so SQS retries (eventually DLQ).
        with pytest.raises(RuntimeError):
            worker.lambda_handler(record, None)
