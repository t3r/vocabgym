"""Tests for GET /progress/overview — the 'Letzte Übungen' (recent sessions) list.

Regression: the sessions table's sort key is sessionId (a random UUID), so the
query order does NOT reflect recency. The handler must order recentSessions by
completedAt descending, otherwise the 'Letzte Übungen' list appears randomly
ordered. This pins that ordering with sessionIds deliberately chosen so their
UUID order is the OPPOSITE of their completedAt order.
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

_PROG_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'functions', 'progress_handler', 'app.py'
)

_ENV = {
    'PROGRESS_TABLE': 'po-progress',
    'SESSIONS_TABLE': 'po-sessions',
    'VOCABSETS_TABLE': 'po-vocabsets',
    'VOCABITEMS_TABLE': 'po-vocabitems',
    'USERS_TABLE': 'po-users',
    'LEAGUES_TABLE': 'po-leagues',
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
    spec = importlib.util.spec_from_file_location('prog_app_overview', _PROG_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tables(dynamodb):
    dynamodb.create_table(
        TableName='po-vocabsets',
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
        TableName='po-sessions',
        KeySchema=[
            {'AttributeName': 'userId', 'KeyType': 'HASH'},
            {'AttributeName': 'sessionId', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'userId', 'AttributeType': 'S'},
            {'AttributeName': 'sessionId', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    dynamodb.create_table(
        TableName='po-progress',
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


def _overview_event(user_id='u1'):
    return {
        'httpMethod': 'GET',
        'path': '/progress/overview',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
    }


def _put_session(dynamodb, user_id, session_id, completed_at):
    dynamodb.Table('po-sessions').put_item(Item={
        'userId': user_id,
        'sessionId': session_id,
        'vocabSetId': 'set-1',
        'status': 'completed',
        'score': 80,
        'correctAnswers': 8,
        'totalQuestions': 10,
        'duration': 60,
        'completedAt': completed_at,
        'direction': 'de-fr',
        'mode': 'practice',
    })


@mock_aws
def test_recent_sessions_ordered_by_completed_at_desc():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(dynamodb)

    # sessionIds chosen so their lexical (UUID sort) order is the REVERSE of
    # their completedAt order: 'aaa' < 'bbb' < 'ccc' lexically, but their
    # timestamps are oldest -> newest, i.e. the newest session sorts FIRST by
    # sessionId. Without an explicit completedAt sort the newest would appear
    # last (or randomly). Newest must come first.
    _put_session(dynamodb, 'u1', 'aaa', completed_at=3000)  # newest
    _put_session(dynamodb, 'u1', 'bbb', completed_at=2000)
    _put_session(dynamodb, 'u1', 'ccc', completed_at=1000)  # oldest

    app = _load()
    resp = app.lambda_handler(_overview_event('u1'), None)
    assert resp['statusCode'] == 200
    body = json.loads(resp['body'])
    recent = body['recentSessions']

    completed_ats = [int(s['completedAt']) for s in recent]
    assert completed_ats == [3000, 2000, 1000], (
        f"Recent sessions must be newest-first; got {completed_ats}"
    )


@mock_aws
def test_recent_sessions_limited_to_ten_most_recent():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(dynamodb)

    # 12 sessions; the 10 most recent (by completedAt) must be returned, newest
    # first — even though sessionId order is unrelated to time.
    for i in range(12):
        _put_session(dynamodb, 'u1', f'sess-{i:02d}', completed_at=1000 + i * 100)

    app = _load()
    resp = app.lambda_handler(_overview_event('u1'), None)
    body = json.loads(resp['body'])
    recent = body['recentSessions']

    assert len(recent) == 10
    completed_ats = [int(s['completedAt']) for s in recent]
    assert completed_ats == sorted(completed_ats, reverse=True)
    # Newest (1000 + 11*100 = 2100) present; two oldest (1000, 1100) dropped.
    assert completed_ats[0] == 2100
    assert 1000 not in completed_ats and 1100 not in completed_ats
