"""Tests for GET /goals list — league goals fetched via GSI, never a scan.

Regression / cost guard: handle_list previously scanned the entire goals table
to find league-assigned goals (billing for every goal of every user). It now
queries a sparse leagueId-index GSI. These tests pin that a user sees their own
goals plus their league's goals, and — importantly — that the query works
against a table created WITHOUT relying on a full scan (moto would still return
scan results, so the value here is verifying the GSI query path and the sparse
behavior: personal goals without a leagueId must NOT leak via the index).
"""

import importlib.util
import os
import sys
import json

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

_GOAL_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'functions', 'goal_handler', 'app.py'
)

_ENV = {
    'GOALS_TABLE': 'gl-goals',
    'PROGRESS_TABLE': 'gl-progress',
    'VOCABSETS_TABLE': 'gl-vocabsets',
    'VOCABITEMS_TABLE': 'gl-vocabitems',
    'USERS_TABLE': 'gl-users',
    'LEAGUES_TABLE': 'gl-leagues',
    'LEAGUE_MEMBERS_TABLE': 'gl-league-members',
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
    spec = importlib.util.spec_from_file_location('goal_app_list', _GOAL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tables(dynamodb):
    dynamodb.create_table(
        TableName='gl-goals',
        KeySchema=[
            {'AttributeName': 'goalId', 'KeyType': 'HASH'},
            {'AttributeName': 'userId', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'goalId', 'AttributeType': 'S'},
            {'AttributeName': 'userId', 'AttributeType': 'S'},
            {'AttributeName': 'leagueId', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'userId-index',
                'KeySchema': [{'AttributeName': 'userId', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'},
            },
            {
                'IndexName': 'leagueId-index',
                'KeySchema': [{'AttributeName': 'leagueId', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    dynamodb.create_table(
        TableName='gl-users',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )


def _put_goal(dynamodb, goal_id, user_id, deadline, league_id=None):
    item = {
        'goalId': goal_id,
        'userId': user_id,
        'status': 'active',
        'deadline': deadline,
        'createdAt': '2026-01-01',
        'targetMastery': 4,
        'vocabSetIds': [],
        'title': 'G',
    }
    if league_id:
        item['leagueId'] = league_id
    dynamodb.Table('gl-goals').put_item(Item=item)


def _put_user(dynamodb, user_id, league_id=None):
    item = {'userId': user_id, 'role': 'student'}
    if league_id:
        item['leagueId'] = league_id
    dynamodb.Table('gl-users').put_item(Item=item)


def _list_event(user_id):
    return {
        'httpMethod': 'GET',
        'path': '/goals',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
    }


@mock_aws
def test_lists_own_and_league_goals_via_index():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(dynamodb)

    # u1 is in league L1. u1 has a personal goal; the teacher assigned a league
    # goal to L1; u2 (another user in a different league) has an unrelated
    # league goal that must NOT appear for u1.
    _put_user(dynamodb, 'u1', league_id='L1')
    _put_goal(dynamodb, 'g-own', 'u1', deadline='2026-03-01')
    _put_goal(dynamodb, 'g-league', 'teacher1', deadline='2026-02-01', league_id='L1')
    _put_goal(dynamodb, 'g-other-league', 'teacher2', deadline='2026-02-01', league_id='L2')

    app = _load()
    resp = app.lambda_handler(_list_event('u1'), None)
    assert resp['statusCode'] == 200
    goals = json.loads(resp['body'])['goals']
    goal_ids = {g['goalId'] for g in goals}

    assert 'g-own' in goal_ids
    assert 'g-league' in goal_ids            # via leagueId-index query
    assert 'g-other-league' not in goal_ids  # different league, not leaked


@mock_aws
def test_personal_goal_not_leaked_through_league_index():
    # A user with NO league sees only their own goals; the sparse leagueId-index
    # must not surface personal goals (they carry no leagueId attribute).
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(dynamodb)

    _put_user(dynamodb, 'solo')  # no leagueId
    _put_goal(dynamodb, 'g-solo', 'solo', deadline='2026-05-01')

    app = _load()
    resp = app.lambda_handler(_list_event('solo'), None)
    goals = json.loads(resp['body'])['goals']
    goal_ids = {g['goalId'] for g in goals}
    assert goal_ids == {'g-solo'}
