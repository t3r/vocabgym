"""Tests for the identiconSet profile preference (GET/PUT /users/profile)."""

import importlib.util
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
    'USERS_TABLE': 'pf-users',
    'LEAGUES_TABLE': 'pf-leagues',
    'LEAGUE_MEMBERS_TABLE': 'pf-members',
    'VOCABSETS_TABLE': 'pf-vocabsets',
    'PROGRESS_TABLE': 'pf-progress',
    'SESSIONS_TABLE': 'pf-sessions',
    'IMAGES_BUCKET': 'pf-images',
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
    spec = importlib.util.spec_from_file_location('league_app_profile', _LEAGUE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _users_table():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    return ddb.create_table(
        TableName='pf-users',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )


def _event(method, body=None):
    e = {
        'httpMethod': method,
        'path': '/users/profile',
        'resource': '/users/profile',
        'requestContext': {'authorizer': {'claims': {'sub': 'u1'}}},
    }
    if body is not None:
        e['body'] = body
    return e


@mock_aws
def test_get_profile_default_identicon_set():
    _users_table()
    app = _load(_ENV)
    resp = app.handle_get_profile(_event('GET'), 'u1')
    assert resp['statusCode'] == 200
    import json
    assert json.loads(resp['body'])['identiconSet'] == 'set1'


@mock_aws
def test_put_profile_sets_identicon_set():
    _users_table()
    app = _load(_ENV)
    import json
    resp = app.handle_update_profile(_event('PUT', '{"identiconSet": "set4"}'), 'u1')
    assert resp['statusCode'] == 200
    assert json.loads(resp['body'])['identiconSet'] == 'set4'
    # Persisted + returned by GET
    resp2 = app.handle_get_profile(_event('GET'), 'u1')
    assert json.loads(resp2['body'])['identiconSet'] == 'set4'


@mock_aws
def test_put_profile_rejects_invalid_identicon_set():
    _users_table()
    app = _load(_ENV)
    resp = app.handle_update_profile(_event('PUT', '{"identiconSet": "set9"}'), 'u1')
    assert resp['statusCode'] == 400


@mock_aws
def test_put_profile_preserves_other_preferences():
    users = _users_table()
    users.put_item(Item={'userId': 'u1', 'preferences': {'sessionLength': 20}})
    app = _load(_ENV)
    app.handle_update_profile(_event('PUT', '{"identiconSet": "set4"}'), 'u1')
    stored = users.get_item(Key={'userId': 'u1'})['Item']['preferences']
    assert stored['identiconSet'] == 'set4'
    assert int(stored['sessionLength']) == 20  # untouched


@mock_aws
def test_get_profile_defaults_ui_language_and_timezone():
    _users_table()
    app = _load(_ENV)
    import json
    resp = app.handle_get_profile(_event('GET'), 'u1')
    assert resp['statusCode'] == 200
    body = json.loads(resp['body'])
    assert body['uiLanguage'] == 'de'
    assert body['timezone'] == 'Europe/Berlin'


@mock_aws
def test_put_profile_sets_ui_language_and_timezone():
    _users_table()
    app = _load(_ENV)
    import json
    resp = app.handle_update_profile(
        _event('PUT', '{"uiLanguage": "en", "timezone": "America/New_York"}'), 'u1'
    )
    assert resp['statusCode'] == 200
    body = json.loads(resp['body'])
    assert body['uiLanguage'] == 'en'
    assert body['timezone'] == 'America/New_York'
    # Persisted + returned by GET
    resp2 = app.handle_get_profile(_event('GET'), 'u1')
    body2 = json.loads(resp2['body'])
    assert body2['uiLanguage'] == 'en'
    assert body2['timezone'] == 'America/New_York'


@mock_aws
def test_put_profile_rejects_invalid_ui_language():
    _users_table()
    app = _load(_ENV)
    resp = app.handle_update_profile(_event('PUT', '{"uiLanguage": "xx"}'), 'u1')
    assert resp['statusCode'] == 400


@mock_aws
def test_put_profile_rejects_invalid_timezone():
    _users_table()
    app = _load(_ENV)
    resp = app.handle_update_profile(_event('PUT', '{"timezone": "Mars/Olympus"}'), 'u1')
    assert resp['statusCode'] == 400


@mock_aws
def test_put_profile_prefs_merge_ui_language_and_icon_and_existing():
    users = _users_table()
    users.put_item(Item={'userId': 'u1', 'preferences': {'sessionLength': 20}})
    app = _load(_ENV)
    app.handle_update_profile(
        _event('PUT', '{"identiconSet": "set4", "uiLanguage": "es"}'), 'u1'
    )
    stored = users.get_item(Key={'userId': 'u1'})['Item']['preferences']
    assert stored['identiconSet'] == 'set4'
    assert stored['uiLanguage'] == 'es'
    assert int(stored['sessionLength']) == 20  # untouched


@mock_aws
def test_put_profile_still_requires_at_least_one_field():
    _users_table()
    app = _load(_ENV)
    resp = app.handle_update_profile(_event('PUT', '{}'), 'u1')
    assert resp['statusCode'] == 400
