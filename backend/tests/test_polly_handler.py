"""Tests for the Polly TTS handler (voices + synthesize).

Covers:
- GET /tts/voices: standard-engine filter + grouping by accent, unknown lang
- _speakable_text: keeps article, truncates at ';'/','
- POST /tts/synthesize: ownership (404 on foreign/missing set), invalid voice
  (400), cache hit (no Polly call, no rate count), cache miss (Polly + S3 put),
  rate-limit (429 after limit)
"""

import json
import os
import sys
import importlib.util
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_test_dir = os.path.dirname(__file__)
_backend_dir = os.path.join(_test_dir, '..')
sys.path.insert(0, os.path.join(_backend_dir, 'layers', 'shared', 'python'))
sys.path.insert(0, os.path.join(_backend_dir, 'functions', 'polly_handler'))

# ---------------------------------------------------------------------------
# Env + credentials (before boto3 usage)
# ---------------------------------------------------------------------------
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
for _key in ('AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN',
             'AWS_CREDENTIAL_EXPIRATION', 'AWS_SESSION_EXPIRATION', 'AWS_PROFILE'):
    os.environ.pop(_key, None)

os.environ.setdefault('IMAGES_BUCKET', 'test-images')
os.environ.setdefault('VOCABSETS_TABLE', 'test-vocabsets')
os.environ.setdefault('VOCABITEMS_TABLE', 'test-vocabitems')
os.environ.setdefault('TTS_USAGE_TABLE', 'test-tts-usage')
os.environ.setdefault('REGION', 'eu-central-1')
os.environ.setdefault('ENVIRONMENT', 'test')

import boto3
from moto import mock_aws


# Sample describe_voices response (mixed languages/engines)
DESCRIBE_VOICES_RESPONSE = {
    'Voices': [
        {'Id': 'Amy', 'Name': 'Amy', 'Gender': 'Female', 'LanguageCode': 'en-GB',
         'SupportedEngines': ['standard', 'neural']},
        {'Id': 'Brian', 'Name': 'Brian', 'Gender': 'Male', 'LanguageCode': 'en-GB',
         'SupportedEngines': ['standard']},
        {'Id': 'Joanna', 'Name': 'Joanna', 'Gender': 'Female', 'LanguageCode': 'en-US',
         'SupportedEngines': ['standard', 'neural']},
        {'Id': 'Olivia', 'Name': 'Olivia', 'Gender': 'Female', 'LanguageCode': 'en-AU',
         'SupportedEngines': ['neural']},  # neural-only -> must be filtered out
        {'Id': 'Nicole', 'Name': 'Nicole', 'Gender': 'Female', 'LanguageCode': 'en-AU',
         'SupportedEngines': ['standard']},
        {'Id': 'Celine', 'Name': 'Céline', 'Gender': 'Female', 'LanguageCode': 'fr-FR',
         'SupportedEngines': ['standard']},
        {'Id': 'Marlene', 'Name': 'Marlene', 'Gender': 'Female', 'LanguageCode': 'de-DE',
         'SupportedEngines': ['standard']},  # different lang -> excluded for en
    ],
}


def _make_event(method, path, query=None, body=None, user_id='user-1'):
    return {
        'httpMethod': method,
        'path': path,
        'queryStringParameters': query,
        'body': json.dumps(body) if body is not None else None,
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
    }


@pytest.fixture()
def polly_app():
    """Load polly_handler under moto with mocked S3/DynamoDB and a stubbed Polly."""
    with mock_aws():
        ddb = boto3.resource('dynamodb', region_name='eu-central-1')
        s3 = boto3.client('s3', region_name='eu-central-1')

        # S3 bucket
        s3.create_bucket(
            Bucket=os.environ['IMAGES_BUCKET'],
            CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'},
        )

        # VocabSets table (PK vocabSetId, SK userId)
        ddb.create_table(
            TableName=os.environ['VOCABSETS_TABLE'],
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
        # VocabItems table (PK vocabSetId, SK itemId)
        ddb.create_table(
            TableName=os.environ['VOCABITEMS_TABLE'],
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
        # TTS usage table (PK userId, SK windowStart)
        ddb.create_table(
            TableName=os.environ['TTS_USAGE_TABLE'],
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

        # Fresh import of the module inside the mock context
        module_path = os.path.join(_backend_dir, 'functions', 'polly_handler', 'app.py')
        spec = importlib.util.spec_from_file_location('polly_handler_app', module_path)
        app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app)

        # Patch AWS clients to the mocked resources
        app.dynamodb = ddb
        app.s3_client = s3

        # Stub Polly
        polly = MagicMock()
        polly.describe_voices.return_value = DESCRIBE_VOICES_RESPONSE
        polly.synthesize_speech.return_value = {'AudioStream': MagicMock(read=lambda: b'MP3DATA')}
        app.polly_client = polly
        app._voice_cache.clear()

        yield app, ddb, s3, polly


def _seed_vocab(ddb, vocab_set_id='vs-1', user_id='user-1', item_id='item-1',
                target='the house', lang='en'):
    ddb.Table(os.environ['VOCABSETS_TABLE']).put_item(Item={
        'vocabSetId': vocab_set_id, 'userId': user_id, 'targetLanguage': lang,
    })
    ddb.Table(os.environ['VOCABITEMS_TABLE']).put_item(Item={
        'vocabSetId': vocab_set_id, 'itemId': item_id, 'source': 'das Haus',
        'target': target, 'isActive': True,
    })


# ======================================================================
# GET /tts/voices
# ======================================================================

class TestVoices:
    def test_groups_standard_voices_by_accent(self, polly_app):
        app, _, _, _ = polly_app
        resp = app.lambda_handler(_make_event('GET', '/tts/voices', query={'lang': 'en'}), None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['lang'] == 'en'
        accents = {a['languageCode']: a for a in body['accents']}
        # en-GB, en-US, en-AU present; de-DE excluded
        assert set(accents) == {'en-GB', 'en-US', 'en-AU'}
        # neural-only Olivia filtered out; Nicole (standard) remains for en-AU
        au_voices = {v['voiceId'] for v in accents['en-AU']['voices']}
        assert au_voices == {'Nicole'}
        gb_voices = {v['voiceId'] for v in accents['en-GB']['voices']}
        assert gb_voices == {'Amy', 'Brian'}

    def test_unknown_language_returns_400(self, polly_app):
        app, _, _, _ = polly_app
        resp = app.lambda_handler(_make_event('GET', '/tts/voices', query={'lang': 'xx'}), None)
        assert resp['statusCode'] == 400

    def test_missing_language_returns_400(self, polly_app):
        app, _, _, _ = polly_app
        resp = app.lambda_handler(_make_event('GET', '/tts/voices', query=None), None)
        assert resp['statusCode'] == 400


# ======================================================================
# _speakable_text
# ======================================================================

class TestSpeakableText:
    def test_keeps_article(self, polly_app):
        app, _, _, _ = polly_app
        assert app._speakable_text('la maison') == 'la maison'

    def test_truncates_at_semicolon(self, polly_app):
        app, _, _, _ = polly_app
        assert app._speakable_text('la maison; das Haus') == 'la maison'

    def test_truncates_at_comma(self, polly_app):
        app, _, _, _ = polly_app
        assert app._speakable_text('to run, to rush') == 'to run'

    def test_empty(self, polly_app):
        app, _, _, _ = polly_app
        assert app._speakable_text('') == ''
        assert app._speakable_text(None) == ''


# ======================================================================
# POST /tts/synthesize
# ======================================================================

class TestSynthesize:
    def test_foreign_or_missing_set_returns_404(self, polly_app):
        app, ddb, _, polly = polly_app
        _seed_vocab(ddb, user_id='owner')  # set belongs to 'owner'
        # caller 'user-1' does not own it
        resp = app.lambda_handler(_make_event(
            'POST', '/tts/synthesize',
            body={'vocabSetId': 'vs-1', 'itemId': 'item-1', 'voiceId': 'Brian'},
            user_id='user-1',
        ), None)
        assert resp['statusCode'] == 404
        polly.synthesize_speech.assert_not_called()

    def test_invalid_voice_returns_400(self, polly_app):
        app, ddb, _, polly = polly_app
        _seed_vocab(ddb)
        resp = app.lambda_handler(_make_event(
            'POST', '/tts/synthesize',
            body={'vocabSetId': 'vs-1', 'itemId': 'item-1', 'voiceId': 'Zhiyu'},
        ), None)
        assert resp['statusCode'] == 400
        polly.synthesize_speech.assert_not_called()

    def test_cache_miss_synthesizes_and_stores(self, polly_app):
        app, ddb, s3, polly = polly_app
        _seed_vocab(ddb, target='the house')
        resp = app.lambda_handler(_make_event(
            'POST', '/tts/synthesize',
            body={'vocabSetId': 'vs-1', 'itemId': 'item-1', 'voiceId': 'Brian'},
        ), None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['cached'] is False
        assert 'audioUrl' in body
        polly.synthesize_speech.assert_called_once()
        # verify only the first meaning + article is spoken
        _, kwargs = polly.synthesize_speech.call_args
        assert kwargs['Text'] == 'the house'
        assert kwargs['Engine'] == 'standard'
        assert kwargs['OutputFormat'] == 'mp3'

    def test_cache_hit_skips_polly_and_rate(self, polly_app):
        app, ddb, s3, polly = polly_app
        _seed_vocab(ddb, target='the house')
        body_req = {'vocabSetId': 'vs-1', 'itemId': 'item-1', 'voiceId': 'Brian'}
        # First call: miss
        app.lambda_handler(_make_event('POST', '/tts/synthesize', body=body_req), None)
        assert polly.synthesize_speech.call_count == 1
        # Second call: hit -> no additional Polly call
        resp = app.lambda_handler(_make_event('POST', '/tts/synthesize', body=body_req), None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['cached'] is True
        assert polly.synthesize_speech.call_count == 1  # unchanged

    def test_multiple_meanings_truncated(self, polly_app):
        app, ddb, _, polly = polly_app
        _seed_vocab(ddb, target='to agree; to consent')
        app.lambda_handler(_make_event(
            'POST', '/tts/synthesize',
            body={'vocabSetId': 'vs-1', 'itemId': 'item-1', 'voiceId': 'Amy'},
        ), None)
        _, kwargs = polly.synthesize_speech.call_args
        assert kwargs['Text'] == 'to agree'

    def test_rate_limit_returns_429(self, polly_app):
        app, ddb, _, polly = polly_app
        _seed_vocab(ddb)
        app.RATE_LIMIT_PER_HOUR = 3  # lower for the test

        # Each call uses a distinct word so every call is a cache miss (counts)
        for i in range(3):
            ddb.Table(os.environ['VOCABITEMS_TABLE']).put_item(Item={
                'vocabSetId': 'vs-1', 'itemId': f'i{i}', 'source': 's', 'target': f'word{i}',
                'isActive': True,
            })
            r = app.lambda_handler(_make_event(
                'POST', '/tts/synthesize',
                body={'vocabSetId': 'vs-1', 'itemId': f'i{i}', 'voiceId': 'Brian'},
            ), None)
            assert r['statusCode'] == 200

        # 4th distinct synthesis exceeds the limit
        ddb.Table(os.environ['VOCABITEMS_TABLE']).put_item(Item={
            'vocabSetId': 'vs-1', 'itemId': 'i9', 'source': 's', 'target': 'word9',
            'isActive': True,
        })
        r = app.lambda_handler(_make_event(
            'POST', '/tts/synthesize',
            body={'vocabSetId': 'vs-1', 'itemId': 'i9', 'voiceId': 'Brian'},
        ), None)
        assert r['statusCode'] == 429

    def test_missing_fields_returns_400(self, polly_app):
        app, ddb, _, _ = polly_app
        _seed_vocab(ddb)
        resp = app.lambda_handler(_make_event(
            'POST', '/tts/synthesize', body={'vocabSetId': 'vs-1'},
        ), None)
        assert resp['statusCode'] == 400


# ======================================================================
# League-set access: a student may synthesize a word from a set assigned
# to their league (owned by the teacher), not just their own sets.
# Uses standalone @mock_aws functions (no fixture nesting) to stay stable.
# ======================================================================

def _load_polly_with_league_tables():
    """Create all tables (incl. Users + Leagues) and import the handler fresh
    inside the active mock. Caller must be under @mock_aws."""
    import importlib
    os.environ['USERS_TABLE'] = 'test-users'
    os.environ['LEAGUES_TABLE'] = 'test-leagues'
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(Bucket=os.environ['IMAGES_BUCKET'],
                     CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'})
    for name, keys in (
        (os.environ['VOCABSETS_TABLE'], [('vocabSetId', 'HASH'), ('userId', 'RANGE')]),
        (os.environ['VOCABITEMS_TABLE'], [('vocabSetId', 'HASH'), ('itemId', 'RANGE')]),
        (os.environ['TTS_USAGE_TABLE'], [('userId', 'HASH'), ('windowStart', 'RANGE')]),
        ('test-users', [('userId', 'HASH')]),
        ('test-leagues', [('leagueId', 'HASH')]),
    ):
        ddb.create_table(
            TableName=name,
            KeySchema=[{'AttributeName': k, 'KeyType': t} for k, t in keys],
            AttributeDefinitions=[{'AttributeName': k, 'AttributeType': 'S'} for k, _ in keys],
            BillingMode='PAY_PER_REQUEST',
        )
    module_path = os.path.join(_backend_dir, 'functions', 'polly_handler', 'app.py')
    spec = importlib.util.spec_from_file_location('polly_handler_league', module_path)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    app.dynamodb = ddb
    app.s3_client = s3
    polly = MagicMock()
    polly.describe_voices.return_value = DESCRIBE_VOICES_RESPONSE
    polly.synthesize_speech.return_value = {'AudioStream': MagicMock(read=lambda: b'MP3DATA')}
    app.polly_client = polly
    app._voice_cache.clear()
    return app, ddb, polly


@mock_aws
def test_league_member_can_synthesize_teacher_set():
    app, ddb, polly = _load_polly_with_league_tables()
    # Teacher owns the set; student is in a league that has it assigned.
    ddb.Table(os.environ['VOCABSETS_TABLE']).put_item(Item={
        'vocabSetId': 'vs-league', 'userId': 'teacher-1', 'targetLanguage': 'fr'})
    ddb.Table(os.environ['VOCABITEMS_TABLE']).put_item(Item={
        'vocabSetId': 'vs-league', 'itemId': 'it-1',
        'source': 'das Haus', 'target': 'la maison', 'isActive': True})
    ddb.Table('test-users').put_item(Item={'userId': 'student-1', 'leagueId': 'lg-1'})
    ddb.Table('test-leagues').put_item(Item={
        'leagueId': 'lg-1', 'teacherUserId': 'teacher-1', 'vocabSetIds': ['vs-league']})

    resp = app.lambda_handler(_make_event(
        'POST', '/tts/synthesize', user_id='student-1',
        body={'vocabSetId': 'vs-league', 'itemId': 'it-1', 'voiceId': 'Celine'},
    ), None)
    assert resp['statusCode'] == 200, resp['body']
    polly.synthesize_speech.assert_called_once()


@mock_aws
def test_non_member_still_gets_404():
    app, ddb, polly = _load_polly_with_league_tables()
    ddb.Table(os.environ['VOCABSETS_TABLE']).put_item(Item={
        'vocabSetId': 'vs-league', 'userId': 'teacher-1', 'targetLanguage': 'fr'})
    ddb.Table(os.environ['VOCABITEMS_TABLE']).put_item(Item={
        'vocabSetId': 'vs-league', 'itemId': 'it-1',
        'source': 'das Haus', 'target': 'la maison', 'isActive': True})
    ddb.Table('test-users').put_item(Item={'userId': 'outsider'})  # no league
    resp = app.lambda_handler(_make_event(
        'POST', '/tts/synthesize', user_id='outsider',
        body={'vocabSetId': 'vs-league', 'itemId': 'it-1', 'voiceId': 'Celine'},
    ), None)
    assert resp['statusCode'] == 404
    polly.synthesize_speech.assert_not_called()
