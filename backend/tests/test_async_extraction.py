"""Tests for the async extraction flow: enqueuer, worker, page counters."""

import importlib.util
import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'functions', 'extraction_handler'))

for _k in (
    'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
    'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
):
    os.environ.pop(_k, None)
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'

_APP_PATH = os.path.join(os.path.dirname(__file__), '..', 'functions', 'extraction_handler', 'app.py')
_WORKER_PATH = os.path.join(os.path.dirname(__file__), '..', 'functions', 'extraction_handler', 'worker.py')

_ENV = {
    'IMAGES_BUCKET': 'ax-images',
    'VOCABSETS_TABLE': 'ax-vocabsets',
    'VOCABITEMS_TABLE': 'ax-vocabitems',
    'EXTRACTION_USAGE_TABLE': 'ax-usage',
    'EXTRACTION_QUEUE_URL': '',  # set per-test after queue creation
    'REGION': 'eu-central-1',
    'EXTRACTION_LIMIT_PER_DAY': '100',
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
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _make_tables(ddb):
    ddb.create_table(
        TableName='ax-vocabsets',
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
        TableName='ax-vocabitems',
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
        TableName='ax-usage',
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


def _api_event(body, user_id='u1'):
    return {
        'httpMethod': 'POST',
        'path': '/vocab/process',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
        'body': json.dumps(body),
    }


# ======================================================================
# Enqueuer: POST /vocab/process
# ======================================================================

@mock_aws
def test_enqueue_sends_one_message_per_page_and_returns_202():
    import uuid
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _make_tables(ddb)
    sqs = boto3.client('sqs', region_name='eu-central-1')
    qurl = sqs.create_queue(QueueName='ax-queue')['QueueUrl']

    set_id = str(uuid.uuid4())
    keys = [f'images/u1/{set_id}/1-original.jpg', f'images/u1/{set_id}/2-original.jpg']
    ddb.Table('ax-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': 'u1', 'title': 'X',
        'imageKeys': keys, 'sourceImageKey': keys[0],
        'extractionStatus': 'pending', 'targetLanguage': 'fr',
    })

    app = _load(_APP_PATH, 'app', {**_ENV, 'EXTRACTION_QUEUE_URL': qurl})
    resp = app.handle_process(_api_event({'vocabSetId': set_id}), 'u1')

    assert resp['statusCode'] == 202
    body = json.loads(resp['body'])
    assert body['status'] == 'processing'
    assert body['pagesTotal'] == 2

    # Two messages enqueued
    msgs = sqs.receive_message(QueueUrl=qurl, MaxNumberOfMessages=10).get('Messages', [])
    assert len(msgs) == 2

    # Counters initialised on the set
    item = ddb.Table('ax-vocabsets').get_item(Key={'vocabSetId': set_id, 'userId': 'u1'})['Item']
    assert int(item['pagesTotal']) == 2
    assert int(item['pagesDone']) == 0
    assert int(item['pagesFailed']) == 0
    assert item['extractionStatus'] == 'processing'


@mock_aws
def test_enqueue_foreign_set_returns_404():
    import uuid
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _make_tables(ddb)
    sqs = boto3.client('sqs', region_name='eu-central-1')
    qurl = sqs.create_queue(QueueName='ax-queue')['QueueUrl']
    set_id = str(uuid.uuid4())
    # set belongs to someone else
    ddb.Table('ax-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': 'owner', 'imageKeys': ['k'],
    })
    app = _load(_APP_PATH, 'app', {**_ENV, 'EXTRACTION_QUEUE_URL': qurl})
    resp = app.handle_process(_api_event({'vocabSetId': set_id}, user_id='intruder'), 'intruder')
    assert resp['statusCode'] == 404


# ======================================================================
# record_page_result: atomic counters + finalisation
# ======================================================================

@mock_aws
def test_record_page_result_finalises_to_review_on_last_page():
    import uuid
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _make_tables(ddb)
    app = _load(_APP_PATH, 'app', _ENV)
    set_id = str(uuid.uuid4())
    ddb.Table('ax-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': 'u1',
        'extractionStatus': 'processing', 'pagesTotal': 2, 'pagesDone': 0, 'pagesFailed': 0,
    })

    app.record_page_result(set_id, 'u1', True)   # page 1 ok
    mid = ddb.Table('ax-vocabsets').get_item(Key={'vocabSetId': set_id, 'userId': 'u1'})['Item']
    assert mid['extractionStatus'] == 'processing'  # not done yet
    assert int(mid['pagesDone']) == 1

    app.record_page_result(set_id, 'u1', False)  # page 2 failed → all done
    end = ddb.Table('ax-vocabsets').get_item(Key={'vocabSetId': set_id, 'userId': 'u1'})['Item']
    assert end['extractionStatus'] == 'review'   # at least one page ok → review
    assert int(end['pagesDone']) == 1
    assert int(end['pagesFailed']) == 1


@mock_aws
def test_record_page_result_all_failed_becomes_failed():
    import uuid
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _make_tables(ddb)
    app = _load(_APP_PATH, 'app', _ENV)
    set_id = str(uuid.uuid4())
    ddb.Table('ax-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': 'u1',
        'extractionStatus': 'processing', 'pagesTotal': 1, 'pagesDone': 0, 'pagesFailed': 0,
    })
    app.record_page_result(set_id, 'u1', False)
    end = ddb.Table('ax-vocabsets').get_item(Key={'vocabSetId': set_id, 'userId': 'u1'})['Item']
    assert end['extractionStatus'] == 'failed'


# ======================================================================
# Worker: idempotency + processing
# ======================================================================

@mock_aws
def test_worker_processes_and_counts(monkeypatch):
    import uuid
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _make_tables(ddb)
    app = _load(_APP_PATH, 'app', _ENV)
    worker = _load(_WORKER_PATH, 'worker', _ENV)

    set_id = str(uuid.uuid4())
    key = f'images/u1/{set_id}/1-original.jpg'
    ddb.Table('ax-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': 'u1',
        'extractionStatus': 'processing', 'pagesTotal': 1, 'pagesDone': 0, 'pagesFailed': 0,
    })

    # Stub the heavy extraction to a success with 3 items.
    calls = []
    def fake_process(vsid, uid, ik, tl=''):
        calls.append(ik)
        return True, 3
    monkeypatch.setattr(app, 'process_single_image', fake_process)

    sqs_event = {'Records': [{'body': json.dumps({
        'vocabSetId': set_id, 'userId': 'u1', 'imageKey': key, 'targetLanguage': 'fr',
    })}]}
    worker.lambda_handler(sqs_event, None)

    assert calls == [key]
    end = ddb.Table('ax-vocabsets').get_item(Key={'vocabSetId': set_id, 'userId': 'u1'})['Item']
    assert int(end['pagesDone']) == 1
    assert end['extractionStatus'] == 'review'


@mock_aws
def test_worker_idempotent_on_duplicate_delivery(monkeypatch):
    import uuid
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _make_tables(ddb)
    app = _load(_APP_PATH, 'app', _ENV)
    worker = _load(_WORKER_PATH, 'worker', _ENV)

    set_id = str(uuid.uuid4())
    key = f'images/u1/{set_id}/1-original.jpg'
    ddb.Table('ax-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': 'u1',
        'extractionStatus': 'processing', 'pagesTotal': 1, 'pagesDone': 0, 'pagesFailed': 0,
    })

    calls = []
    monkeypatch.setattr(app, 'process_single_image', lambda *a, **k: (calls.append(1), (True, 2))[1])

    msg = {'Records': [{'body': json.dumps({
        'vocabSetId': set_id, 'userId': 'u1', 'imageKey': key, 'targetLanguage': 'fr',
    })}]}
    worker.lambda_handler(msg, None)
    worker.lambda_handler(msg, None)  # duplicate delivery

    # Processed only once; counter not double-incremented.
    assert len(calls) == 1
    end = ddb.Table('ax-vocabsets').get_item(Key={'vocabSetId': set_id, 'userId': 'u1'})['Item']
    assert int(end['pagesDone']) == 1


@mock_aws
def test_worker_skips_malformed_message():
    import uuid
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _make_tables(ddb)
    _load(_APP_PATH, 'app', _ENV)
    worker = _load(_WORKER_PATH, 'worker', _ENV)
    # Should not raise
    worker.lambda_handler({'Records': [{'body': 'not-json'}]}, None)
    worker.lambda_handler({'Records': [{'body': json.dumps({'vocabSetId': 'x'})}]}, None)
