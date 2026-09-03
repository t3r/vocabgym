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
    dynamodb.create_table(
        TableName='po-users',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    dynamodb.create_table(
        TableName='po-leagues',
        KeySchema=[{'AttributeName': 'leagueId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'leagueId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    dynamodb.create_table(
        TableName='po-vocabitems',
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


# ---------------------------------------------------------------------------
# Regression: a league-only student (owns NO sets) practises league-assigned
# sets. The overview must aggregate progress over those league sets too — not
# just owned sets — otherwise the mastery distribution / accuracy / word counts
# all show 0 despite plenty of progress.
# ---------------------------------------------------------------------------

def _put_set(dynamodb, set_id, owner_id, title, item_count, created=100):
    dynamodb.Table('po-vocabsets').put_item(Item={
        'vocabSetId': set_id, 'userId': owner_id, 'title': title,
        'itemCount': item_count, 'createdAt': created,
    })


def _put_progress(dynamodb, user_id, set_id, item_id, mastery, correct, incorrect):
    dynamodb.Table('po-progress').put_item(Item={
        'progressKey': f'{user_id}#{set_id}', 'itemId': item_id,
        'masteryLevel': mastery, 'correctCount': correct, 'incorrectCount': incorrect,
    })


@mock_aws
def test_league_student_without_own_sets_gets_aggregated_progress():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(dynamodb)

    # Teacher owns the set; student is in the league it's assigned to.
    _put_set(dynamodb, 'league-set', 'teacher-1', 'Liga-Set', item_count=3)
    dynamodb.Table('po-leagues').put_item(Item={
        'leagueId': 'L1', 'teacherUserId': 'teacher-1', 'vocabSetIds': ['league-set'],
    })
    dynamodb.Table('po-users').put_item(Item={'userId': 'student', 'leagueId': 'L1'})

    # Student has progress on the league set (no owned sets at all).
    _put_progress(dynamodb, 'student', 'league-set', 'i1', mastery=5, correct=5, incorrect=0)
    _put_progress(dynamodb, 'student', 'league-set', 'i2', mastery=3, correct=3, incorrect=1)
    _put_progress(dynamodb, 'student', 'league-set', 'i3', mastery=1, correct=1, incorrect=2)

    app = _load()
    resp = app.lambda_handler(_overview_event('student'), None)
    assert resp['statusCode'] == 200
    body = json.loads(resp['body'])

    # Was 0 before the fix; now reflects the league set.
    assert body['totalVocabSets'] == 1
    assert body['totalWords'] == 3
    assert body['practicedWords'] == 3
    assert body['averageMastery'] == 3.0  # (5+3+1)/3
    # accuracy = 9 correct / 12 attempts = 75%
    assert body['overallAccuracy'] == 75.0
    dist = body['masteryDistribution']
    assert dist['5'] == 1 and dist['3'] == 1 and dist['1'] == 1
    # sum of the distribution equals practiced words
    assert sum(int(v) for v in dist.values()) == 3


@mock_aws
def test_activity_by_day_aggregates_recent_sessions():
    import time
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(dynamodb)

    now = int(time.time())
    day = 24 * 60 * 60
    # Two sessions today, one three days ago -> 2 distinct activity points.
    _put_session(dynamodb, 'u1', 's-a', completed_at=now - 60)
    _put_session(dynamodb, 'u1', 's-b', completed_at=now - 120)
    _put_session(dynamodb, 'u1', 's-c', completed_at=now - 3 * day)
    # One ancient session (older than the 30-day window) must be excluded.
    _put_session(dynamodb, 'u1', 's-old', completed_at=now - 40 * day)

    app = _load()
    resp = app.lambda_handler(_overview_event('u1'), None)
    body = json.loads(resp['body'])
    activity = body['activityByDay']

    # 2 days within the window (today + 3-days-ago); ancient one excluded.
    assert len(activity) == 2
    # Ordered oldest -> newest.
    dates = [p['date'] for p in activity]
    assert dates == sorted(dates)
    # Each point exposes correct/total/accuracy/sessions.
    today_point = activity[-1]
    assert today_point['sessions'] == 2
    assert today_point['correct'] == 16  # 8 + 8
    assert today_point['total'] == 20
    assert today_point['accuracy'] == 80


# ---------------------------------------------------------------------------
# Mastery forecast: estimate when the learner reaches "sicher" (all >= level 4).
# ---------------------------------------------------------------------------

@mock_aws
def test_forecast_projects_days_for_partially_secured_learner():
    app = _load()
    # 52 secured (L4/L5), 23 weak practised, 1 untrained -> 24 remaining.
    dist = {0: 1, 1: 5, 2: 5, 3: 12, 4: 0, 5: 52}
    fc = app._mastery_forecast(mastery_distribution=dist, total_words=76,
                               practiced_words=75, active_days=5)
    assert fc['securedWords'] == 52
    assert fc['remainingWords'] == 24
    assert fc['alreadySecured'] is False
    assert fc['estimatedDays'] and fc['estimatedDays'] > 0
    assert 'estimatedDate' in fc
    # The note must mention the remaining count and the "hartnäckigen" caveat.
    assert '24' in fc['note']
    assert 'hartnäckig' in fc['note'].lower()


@mock_aws
def test_forecast_all_secured():
    app = _load()
    dist = {4: 3, 5: 7}  # all 10 words secured
    fc = app._mastery_forecast(mastery_distribution=dist, total_words=10,
                               practiced_words=10, active_days=4)
    assert fc['alreadySecured'] is True
    assert fc['remainingWords'] == 0
    assert fc['estimatedDays'] == 0


@mock_aws
def test_forecast_insufficient_data():
    app = _load()
    # Nothing secured yet -> no rate to project.
    dist = {0: 5, 1: 3}
    fc = app._mastery_forecast(mastery_distribution=dist, total_words=8,
                               practiced_words=8, active_days=1)
    assert fc['estimatedDays'] is None
    assert fc['securedWords'] == 0


@mock_aws
def test_overview_includes_forecast_field():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _tables(dynamodb)
    _put_set(dynamodb, 'set-1', 'u1', 'Mein Set', item_count=2, created=100)
    _put_progress(dynamodb, 'u1', 'set-1', 'i1', mastery=5, correct=5, incorrect=0)
    _put_progress(dynamodb, 'u1', 'set-1', 'i2', mastery=2, correct=2, incorrect=3)

    app = _load()
    resp = app.lambda_handler(_overview_event('u1'), None)
    body = json.loads(resp['body'])
    assert 'forecast' in body
    assert body['forecast']['totalWords'] == 2
