"""Tests for POST /league/leave (student leaves a league)."""

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
    'USERS_TABLE': 'll-users',
    'LEAGUES_TABLE': 'll-leagues',
    'LEAGUE_MEMBERS_TABLE': 'll-members',
    'VOCABSETS_TABLE': 'll-vocabsets',
    'PROGRESS_TABLE': 'll-progress',
    'SESSIONS_TABLE': 'll-sessions',
    'IMAGES_BUCKET': 'll-images',
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


def _load(env):
    for k, v in env.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location('league_app_leave', _LEAGUE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tables(ddb):
    ddb.create_table(
        TableName='ll-users',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName='ll-leagues',
        KeySchema=[{'AttributeName': 'leagueId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'leagueId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName='ll-members',
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


def _event(user_id='student-1'):
    return {
        'httpMethod': 'POST',
        'path': '/league/leave',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
        'body': None,
    }


@mock_aws
def test_student_leaves_league():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('ll-users').put_item(Item={'userId': 'student-1', 'leagueId': 'lg-1', 'role': 'student'})
    ddb.Table('ll-leagues').put_item(Item={'leagueId': 'lg-1', 'teacherUserId': 'teacher-1', 'joinCode': 'ABC123'})
    ddb.Table('ll-members').put_item(Item={'leagueId': 'lg-1', 'userId': 'student-1', 'role': 'student'})

    app = _load(_ENV)
    resp = app.handle_leave(_event('student-1'), 'student-1')
    assert resp['statusCode'] == 200

    user = ddb.Table('ll-users').get_item(Key={'userId': 'student-1'})['Item']
    assert 'leagueId' not in user
    m = ddb.Table('ll-members').get_item(Key={'leagueId': 'lg-1', 'userId': 'student-1'})
    assert 'Item' not in m


@mock_aws
def test_leave_when_not_in_league_returns_400():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('ll-users').put_item(Item={'userId': 'student-1', 'role': 'student'})  # no leagueId
    app = _load(_ENV)
    resp = app.handle_leave(_event('student-1'), 'student-1')
    assert resp['statusCode'] == 400


@mock_aws
def test_teacher_cannot_leave_own_league():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('ll-users').put_item(Item={'userId': 'teacher-1', 'leagueId': 'lg-1', 'role': 'teacher'})
    ddb.Table('ll-leagues').put_item(Item={'leagueId': 'lg-1', 'teacherUserId': 'teacher-1', 'joinCode': 'ABC123'})
    app = _load(_ENV)
    resp = app.handle_leave(_event('teacher-1'), 'teacher-1')
    assert resp['statusCode'] == 400
    assert 'löschen' in json.loads(resp['body'])['error'].lower()


@mock_aws
def test_leave_routes_through_lambda_handler():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(ddb)
    ddb.Table('ll-users').put_item(Item={'userId': 'student-1', 'leagueId': 'lg-1', 'role': 'student'})
    ddb.Table('ll-leagues').put_item(Item={'leagueId': 'lg-1', 'teacherUserId': 'teacher-1', 'joinCode': 'ABC123'})
    ddb.Table('ll-members').put_item(Item={'leagueId': 'lg-1', 'userId': 'student-1', 'role': 'student'})
    app = _load(_ENV)
    resp = app.lambda_handler(_event('student-1'), None)
    assert resp['statusCode'] == 200
