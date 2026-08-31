"""Tests for the league-join teacher guard and profile leagueId hydration.

Covers two bug fixes:
  #1 GET /users/profile returns leagueId (frontend hydrates membership from the
     server record, not just localStorage).
  #2 POST /league/join refuses teachers and refuses joining a league you own
     (prevents an orphaned LeagueMembers row / teacher on their own leaderboard).
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

_LEAGUE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'functions', 'league_handler', 'app.py'
)

_ENV = {
    'USERS_TABLE': 'lj-users',
    'LEAGUES_TABLE': 'lj-leagues',
    'LEAGUE_MEMBERS_TABLE': 'lj-members',
    'VOCABSETS_TABLE': 'lj-vocabsets',
    'PROGRESS_TABLE': 'lj-progress',
    'SESSIONS_TABLE': 'lj-sessions',
    'IMAGES_BUCKET': 'lj-images',
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


def _load(env=_ENV):
    for k, v in env.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location('league_app_join', _LEAGUE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tables(ddb):
    ddb.create_table(
        TableName='lj-users',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName='lj-leagues',
        KeySchema=[{'AttributeName': 'leagueId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[
            {'AttributeName': 'leagueId', 'AttributeType': 'S'},
            {'AttributeName': 'joinCode', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'joinCode-index',
            'KeySchema': [{'AttributeName': 'joinCode', 'KeyType': 'HASH'}],
            'Projection': {'ProjectionType': 'ALL'},
        }],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName='lj-members',
        KeySchema=[
            {'AttributeName': 'leagueId', 'KeyType': 'HASH'},
            {'AttributeName': 'userId', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'leagueId', 'AttributeType': 'S'},
            {'AttributeName': 'userId', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )


def _join_event(user_id, join_code, groups=None):
    claims = {'sub': user_id}
    if groups is not None:
        claims['cognito:groups'] = groups
    return {
        'httpMethod': 'POST',
        'path': '/league/join',
        'requestContext': {'authorizer': {'claims': claims}},
        'body': json.dumps({'joinCode': join_code}),
    }


def _profile_event(user_id):
    return {
        'httpMethod': 'GET',
        'path': '/users/profile',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
        'body': None,
    }


# --- Bug #2: teacher join guard -------------------------------------------

@mock_aws
def test_teacher_group_cannot_join_league():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('lj-users').put_item(Item={'userId': 'teach-1', 'role': 'teacher'})
    ddb.Table('lj-leagues').put_item(Item={
        'leagueId': 'lg-1', 'teacherUserId': 'other-teacher', 'joinCode': 'ABC123'
    })
    app = _load()
    resp = app.handle_join(_join_event('teach-1', 'ABC123', groups='teachers'), 'teach-1')
    assert resp['statusCode'] == 400
    # No member row created.
    m = ddb.Table('lj-members').get_item(Key={'leagueId': 'lg-1', 'userId': 'teach-1'})
    assert 'Item' not in m


@mock_aws
def test_owner_cannot_join_own_league_even_without_group_claim():
    # Defense-in-depth: even if the cognito:groups claim is missing, the
    # league's own teacher must not be added as a member.
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('lj-users').put_item(Item={'userId': 'owner-1', 'role': 'teacher'})
    ddb.Table('lj-leagues').put_item(Item={
        'leagueId': 'lg-1', 'teacherUserId': 'owner-1', 'joinCode': 'XYZ789'
    })
    app = _load()
    resp = app.handle_join(_join_event('owner-1', 'XYZ789'), 'owner-1')  # no groups
    assert resp['statusCode'] == 400
    m = ddb.Table('lj-members').get_item(Key={'leagueId': 'lg-1', 'userId': 'owner-1'})
    assert 'Item' not in m


@mock_aws
def test_student_can_still_join():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('lj-users').put_item(Item={'userId': 'stud-1', 'role': 'student', 'displayName': 'Max'})
    ddb.Table('lj-leagues').put_item(Item={
        'leagueId': 'lg-1', 'teacherUserId': 'teach-1', 'joinCode': 'JOIN01', 'name': 'Klasse 9b'
    })
    app = _load()
    resp = app.handle_join(_join_event('stud-1', 'JOIN01'), 'stud-1')
    assert resp['statusCode'] == 200
    m = ddb.Table('lj-members').get_item(Key={'leagueId': 'lg-1', 'userId': 'stud-1'})
    assert m['Item']['userId'] == 'stud-1'
    user = ddb.Table('lj-users').get_item(Key={'userId': 'stud-1'})['Item']
    assert user['leagueId'] == 'lg-1'


# --- Bug #1: profile returns leagueId -------------------------------------

@mock_aws
def test_profile_returns_league_id_when_member():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('lj-users').put_item(Item={'userId': 'stud-1', 'leagueId': 'lg-1', 'displayName': 'Max'})
    app = _load()
    resp = app.handle_get_profile(_profile_event('stud-1'), 'stud-1')
    assert resp['statusCode'] == 200
    body = json.loads(resp['body'])
    assert body['leagueId'] == 'lg-1'


@mock_aws
def test_profile_returns_null_league_id_when_not_member():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('lj-users').put_item(Item={'userId': 'stud-1', 'displayName': 'Max'})  # no leagueId
    app = _load()
    resp = app.handle_get_profile(_profile_event('stud-1'), 'stud-1')
    assert resp['statusCode'] == 200
    body = json.loads(resp['body'])
    assert body['leagueId'] is None
