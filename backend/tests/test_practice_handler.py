"""Tests for the practice handler and answer_checker module."""

import json
import os
import sys
import pytest

# Add function and layer to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'functions', 'practice_handler'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))

# Set environment variables
os.environ['IMAGES_BUCKET'] = 'test-images-bucket'
os.environ['VOCABSETS_TABLE'] = 'test-vocabsets-table'
os.environ['VOCABITEMS_TABLE'] = 'test-vocabitems-table'
os.environ['SESSIONS_TABLE'] = 'test-sessions-table'
os.environ['PROGRESS_TABLE'] = 'test-progress-table'
os.environ['REGION'] = 'eu-central-1'
os.environ['ENVIRONMENT'] = 'test'
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'

from answer_checker import (
    normalize_answer,
    levenshtein_distance,
    check_answer,
    get_answer_feedback,
)


class TestNormalizeAnswer:
    """Tests for the normalize_answer function."""

    def test_basic_normalization(self):
        """Test basic string normalization."""
        assert normalize_answer('  Hello  ') == 'hello'
        assert normalize_answer('WORLD') == 'world'

    def test_accent_removal(self):
        """Test that accents/diacritics are removed."""
        assert normalize_answer('café') == 'cafe'
        assert normalize_answer('naïve') == 'naive'
        assert normalize_answer('l\'école') == 'lecole'
        assert normalize_answer('garçon') == 'garcon'
        assert normalize_answer('über') == 'uber'
        # Note: ß is not a diacritical mark, so NFD normalization doesn't change it
        assert normalize_answer('Straße') == 'straße'

    def test_punctuation_removal(self):
        """Test that punctuation is removed."""
        assert normalize_answer('hello!') == 'hello'
        assert normalize_answer('world.') == 'world'
        assert normalize_answer('"test"') == 'test'
        assert normalize_answer('(note)') == ''  # parenthesized content is fully stripped

    def test_whitespace_collapse(self):
        """Test that multiple spaces are collapsed."""
        assert normalize_answer('la  maison') == 'la maison'
        assert normalize_answer('  le   chat  ') == 'le chat'

    def test_empty_input(self):
        """Test empty and None inputs."""
        assert normalize_answer('') == ''
        assert normalize_answer('   ') == ''

    def test_french_special_chars(self):
        """Test common French special characters."""
        assert normalize_answer('français') == 'francais'
        assert normalize_answer('ça va') == 'ca va'
        assert normalize_answer('être') == 'etre'
        assert normalize_answer('où') == 'ou'


class TestLevenshteinDistance:
    """Tests for the levenshtein_distance function."""

    def test_identical_strings(self):
        """Test distance of identical strings is 0."""
        assert levenshtein_distance('hello', 'hello') == 0
        assert levenshtein_distance('', '') == 0

    def test_empty_string(self):
        """Test distance with empty string equals length of other."""
        assert levenshtein_distance('hello', '') == 5
        assert levenshtein_distance('', 'world') == 5

    def test_single_edit(self):
        """Test single character edits."""
        # Substitution
        assert levenshtein_distance('cat', 'bat') == 1
        # Insertion
        assert levenshtein_distance('cat', 'cats') == 1
        # Deletion
        assert levenshtein_distance('cats', 'cat') == 1

    def test_multiple_edits(self):
        """Test multiple character edits."""
        assert levenshtein_distance('kitten', 'sitting') == 3
        assert levenshtein_distance('maison', 'maisom') == 1

    def test_transposition(self):
        """Test character transposition (counts as 2 edits)."""
        assert levenshtein_distance('ab', 'ba') == 2


class TestCheckAnswer:
    """Tests for the check_answer function."""

    def test_exact_match(self):
        """Test exact string match."""
        assert check_answer('la maison', 'la maison') is True
        assert check_answer('der Hund', 'der Hund') is True

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        assert check_answer('La Maison', 'la maison') is True
        assert check_answer('DER HUND', 'der Hund') is True

    def test_accent_tolerance(self):
        """Test that accented and non-accented are equivalent."""
        assert check_answer('cafe', 'café') is True
        assert check_answer('ecole', 'école') is True
        assert check_answer('francais', 'français') is True

    def test_article_tolerance(self):
        """Test matching with and without articles."""
        assert check_answer('maison', 'la maison') is True
        assert check_answer('Hund', 'der Hund') is True
        assert check_answer('ecole', "l'école") is True

    def test_fuzzy_matching_long_words(self):
        """Test fuzzy matching for words > 5 characters (distance ≤ 2)."""
        assert check_answer('maisom', 'maison') is True  # 1 edit
        assert check_answer('maisno', 'maison') is True  # 2 edits (transposition = 2)
        assert check_answer('ordinatuer', 'ordinateur') is True  # 2 edits

    def test_fuzzy_matching_short_words(self):
        """Test fuzzy matching for words 3-5 characters (distance ≤ 1)."""
        assert check_answer('chai', 'chat') is True  # 1 edit
        assert check_answer('ble', 'bleu') is True  # 1 edit

    def test_very_short_words_exact_only(self):
        """Test that very short words (< 3 chars) require exact match."""
        assert check_answer('le', 'la') is False  # 1 edit but word too short

    def test_wrong_answers(self):
        """Test clearly wrong answers are rejected."""
        assert check_answer('dog', 'la maison') is False
        assert check_answer('completely wrong', 'école') is False
        assert check_answer('', 'maison') is False

    def test_whitespace_handling(self):
        """Test that extra whitespace is handled."""
        assert check_answer('  la maison  ', 'la maison') is True
        assert check_answer('la  maison', 'la maison') is True

    def test_punctuation_handling(self):
        """Test that punctuation differences are tolerated."""
        assert check_answer('la maison.', 'la maison') is True
        assert check_answer('l\'école', "l'école") is True

    def test_empty_inputs(self):
        """Test empty inputs return False."""
        assert check_answer('', '') is False
        assert check_answer('test', '') is False
        assert check_answer('', 'test') is False


class TestCheckAnswerMultiOption:
    """Answers with several acceptable meanings separated by '/' or ';'."""

    def test_slash_option_accepted(self):
        assert check_answer('la maison', 'la maison / le logement') is True
        assert check_answer('le logement', 'la maison / le logement') is True

    def test_semicolon_option_accepted(self):
        assert check_answer('la maison', 'la maison; le logement') is True
        assert check_answer('le logement', 'la maison; le logement') is True

    def test_no_option_matches(self):
        assert check_answer('le chat', 'la maison / le logement') is False


class TestCheckAnswerStrict:
    """Exam grading: accents significant, no fuzzy tolerance."""

    def test_exact_with_accents(self):
        assert check_answer('été', 'été', strict=True) is True
        assert check_answer('français', 'français', strict=True) is True

    def test_missing_accent_rejected(self):
        assert check_answer('cafe', 'café', strict=True) is False
        assert check_answer('ete', 'été', strict=True) is False

    def test_wrong_accent_rejected(self):
        assert check_answer('éleve', 'élève', strict=True) is False

    def test_case_still_ignored(self):
        assert check_answer('Café', 'café', strict=True) is True

    def test_punctuation_still_ignored(self):
        assert check_answer('la maison.', 'la maison', strict=True) is True

    def test_no_fuzzy_tolerance(self):
        # A one-char typo is close in practice mode, but wrong in exam mode.
        assert check_answer('maisom', 'maison', strict=True) is False

    def test_article_still_optional(self):
        assert check_answer('maison', 'la maison', strict=True) is True

    def test_slash_option_with_accents(self):
        assert check_answer('été', 'été / la saison chaude', strict=True) is True
        assert check_answer('ete', 'été / la saison chaude', strict=True) is False


class TestGetAnswerFeedback:
    """Tests for the get_answer_feedback function."""

    def test_correct_exact_match(self):
        """Test feedback for exact correct answer."""
        is_correct, message = get_answer_feedback('la maison', 'la maison')
        assert is_correct is True
        assert 'Correct' in message

    def test_correct_fuzzy_match(self):
        """Test feedback for fuzzy correct answer."""
        is_correct, message = get_answer_feedback('maisom', 'maison')
        assert is_correct is True

    def test_incorrect_answer(self):
        """Test feedback for incorrect answer."""
        is_correct, message = get_answer_feedback('le chat', 'la maison')
        assert is_correct is False
        assert 'la maison' in message


class TestPracticeHandlerIntegration:
    """Integration tests for the practice handler with mocked DynamoDB."""

    def test_validate_practice_options(self):
        """Test practice options validation."""
        from lib.validation import validate_practice_options

        # Valid options
        valid, err = validate_practice_options({
            'vocabSetId': '123e4567-e89b-12d3-a456-426614174000',
            'direction': 'de-fr',
            'questionCount': 20,
        })
        assert valid is True

        # Missing vocabSetId
        valid, err = validate_practice_options({'direction': 'de-fr'})
        assert valid is False
        assert 'vocabSetId' in err

        # Invalid direction
        valid, err = validate_practice_options({
            'vocabSetId': '123e4567-e89b-12d3-a456-426614174000',
            'direction': 'invalid',
        })
        assert valid is False
        assert 'Direction' in err

        # Invalid question count
        valid, err = validate_practice_options({
            'vocabSetId': '123e4567-e89b-12d3-a456-426614174000',
            'questionCount': 0,
        })
        assert valid is False

        # Valid focus values
        for f in ('all', 'weak'):
            valid, err = validate_practice_options({
                'vocabSetId': '123e4567-e89b-12d3-a456-426614174000',
                'focus': f,
            })
            assert valid is True, f"focus={f} should be valid"

        # Invalid focus value
        valid, err = validate_practice_options({
            'vocabSetId': '123e4567-e89b-12d3-a456-426614174000',
            'focus': 'bogus',
        })
        assert valid is False
        assert 'focus' in err



# ======================================================================
# Session length cap: a training unit holds at most 10 word pairs.
# ======================================================================

import importlib.util

import boto3
from moto import mock_aws

_PRACTICE_APP_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'functions', 'practice_handler', 'app.py'
)


def _reset_moto_creds():
    for _k in (
        'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
        'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
    ):
        os.environ.pop(_k, None)
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'


def _load_practice_app():
    spec = importlib.util.spec_from_file_location('practice_app_cap', _PRACTICE_APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_tables(ddb):
    ddb.create_table(
        TableName='test-vocabsets-table',
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
        TableName='test-vocabitems-table',
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
        TableName='test-sessions-table',
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
    ddb.create_table(
        TableName='test-progress-table',
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


def _seed_set(ddb, set_id, user_id, n_items):
    ddb.Table('test-vocabsets-table').put_item(Item={
        'vocabSetId': set_id, 'userId': user_id, 'title': 'Big set',
        'extractionStatus': 'approved', 'itemCount': n_items,
    })
    items_table = ddb.Table('test-vocabitems-table')
    for i in range(n_items):
        items_table.put_item(Item={
            'vocabSetId': set_id, 'itemId': f'i{i}',
            'source': f'wort{i}', 'target': f'word{i}',
            'order': i, 'isActive': True,
        })


def _start_event(set_id, user_id, question_count=None):
    body = {'vocabSetId': set_id, 'direction': 'de-fr'}
    if question_count is not None:
        body['questionCount'] = question_count
    return {
        'httpMethod': 'POST',
        'path': '/practice/start',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
        'body': json.dumps(body),
    }


class TestSessionLengthCap:
    """A training unit must never exceed 10 word pairs, even for big sets or a
    client asking for more — while the weighted 'weak words' selection still
    fills those 10 slots from the whole set."""

    @mock_aws
    def test_large_set_capped_to_10(self):
        _reset_moto_creds()
        ddb = boto3.resource('dynamodb', region_name='eu-central-1')
        _make_tables(ddb)
        app = _load_practice_app()
        app.dynamodb = ddb
        _seed_set(ddb, 'set-big', 'u1', n_items=40)

        resp = app.handle_start(_start_event('set-big', 'u1'), 'u1')
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['totalQuestions'] == 10
        assert len(body['questions']) == 10

    @mock_aws
    def test_client_requesting_more_is_capped_to_10(self):
        _reset_moto_creds()
        ddb = boto3.resource('dynamodb', region_name='eu-central-1')
        _make_tables(ddb)
        app = _load_practice_app()
        app.dynamodb = ddb
        _seed_set(ddb, 'set-big', 'u1', n_items=40)

        # Client asks for 20 → server clamps to 10.
        resp = app.handle_start(_start_event('set-big', 'u1', question_count=20), 'u1')
        assert resp['statusCode'] == 200
        assert json.loads(resp['body'])['totalQuestions'] == 10

    @mock_aws
    def test_small_set_not_padded_beyond_its_size(self):
        _reset_moto_creds()
        ddb = boto3.resource('dynamodb', region_name='eu-central-1')
        _make_tables(ddb)
        app = _load_practice_app()
        app.dynamodb = ddb
        _seed_set(ddb, 'set-small', 'u1', n_items=6)

        # 6-word set → 6 questions (cap does not inflate a small set).
        resp = app.handle_start(_start_event('set-small', 'u1'), 'u1')
        assert resp['statusCode'] == 200
        assert json.loads(resp['body'])['totalQuestions'] == 6



# ======================================================================
# handle_complete: must not crash and must update league stats.
# Regression for the prod NameError: _update_league_stats was called but its
# definition had been removed (commit 68957eb) -> every /practice/complete
# returned 500, league points/streak were never written. This end-to-end test
# would have caught it (there was no handle_complete test at all before).
# ======================================================================

os.environ['LEAGUES_TABLE'] = 'test-leagues-table'
os.environ['LEAGUE_MEMBERS_TABLE'] = 'test-league-members-table'
os.environ['USERS_TABLE'] = 'test-users-table'


def _load_practice_app_full():
    for k, v in {
        'LEAGUES_TABLE': 'test-leagues-table',
        'LEAGUE_MEMBERS_TABLE': 'test-league-members-table',
        'USERS_TABLE': 'test-users-table',
    }.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location('practice_app_complete', _PRACTICE_APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_all_tables(ddb):
    _make_tables(ddb)  # vocabsets, vocabitems, sessions, progress
    ddb.create_table(
        TableName='test-users-table',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName='test-leagues-table',
        KeySchema=[{'AttributeName': 'leagueId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'leagueId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )
    ddb.create_table(
        TableName='test-league-members-table',
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


def _complete_event(user_id, session_id):
    return {
        'httpMethod': 'POST',
        'path': '/practice/complete',
        'requestContext': {'authorizer': {'claims': {'sub': user_id}}},
        'body': json.dumps({'sessionId': session_id}),
    }


class TestCompleteSession:
    @mock_aws
    def test_complete_updates_league_stats_and_returns_200(self):
        _reset_moto_creds()
        ddb = boto3.resource('dynamodb', region_name='eu-central-1')
        _make_all_tables(ddb)
        app = _load_practice_app_full()
        app.dynamodb = ddb

        uid, set_id, sid, lid = 'u-alexa', 'set-1', 'sess-1', 'lg-1'
        # League member (starts at zero) — the leaderboard row that must update.
        ddb.Table('test-users-table').put_item(Item={'userId': uid, 'leagueId': lid})
        ddb.Table('test-leagues-table').put_item(Item={
            'leagueId': lid, 'teacherUserId': 'teacher', 'vocabSetIds': [set_id]})
        ddb.Table('test-league-members-table').put_item(Item={
            'leagueId': lid, 'userId': uid, 'displayName': 'Alexa',
            'totalCorrect': 0, 'totalAttempts': 0, 'weeklyCorrect': 0,
            'currentStreak': 0, 'weekStartDate': '', 'lastPracticeDate': ''})
        ddb.Table('test-vocabitems-table').put_item(Item={
            'vocabSetId': set_id, 'itemId': 'i1', 'source': 'Haus', 'target': 'maison',
            'isActive': True})
        # An active session with detailed results to finalise.
        ddb.Table('test-sessions-table').put_item(Item={
            'userId': uid, 'sessionId': sid, 'vocabSetId': set_id, 'status': 'active',
            'startedAt': 1000, 'mode': 'practice',
            'detailedResults': [
                {'itemId': 'i1', 'question': 'Haus', 'correctAnswer': 'maison',
                 'userAnswer': 'maison', 'correct': True},
            ],
        })

        resp = app.handle_complete(_complete_event(uid, sid), uid)

        # Must NOT be a 500 (the NameError regression).
        assert resp['statusCode'] == 200, resp
        body = json.loads(resp['body'])
        assert 'leagueUpdate' in body and body['leagueUpdate'] is not None
        assert body['leagueUpdate']['totalCorrect'] == 1

        # League member row was actually written.
        member = ddb.Table('test-league-members-table').get_item(
            Key={'leagueId': lid, 'userId': uid}).get('Item')
        assert int(member['totalCorrect']) == 1
        assert int(member['totalAttempts']) == 1
        assert int(member['currentStreak']) == 1
        assert member['lastPracticeDate'] != ''

    @mock_aws
    def test_complete_without_league_still_succeeds(self):
        _reset_moto_creds()
        ddb = boto3.resource('dynamodb', region_name='eu-central-1')
        _make_all_tables(ddb)
        app = _load_practice_app_full()
        app.dynamodb = ddb

        uid, set_id, sid = 'u-solo', 'set-2', 'sess-2'
        ddb.Table('test-users-table').put_item(Item={'userId': uid})  # no leagueId
        ddb.Table('test-vocabitems-table').put_item(Item={
            'vocabSetId': set_id, 'itemId': 'i1', 'source': 'Haus', 'target': 'maison',
            'isActive': True})
        ddb.Table('test-sessions-table').put_item(Item={
            'userId': uid, 'sessionId': sid, 'vocabSetId': set_id, 'status': 'active',
            'startedAt': 1000, 'mode': 'practice',
            'detailedResults': [
                {'itemId': 'i1', 'question': 'Haus', 'correctAnswer': 'maison',
                 'userAnswer': 'x', 'correct': False},
            ],
        })

        resp = app.handle_complete(_complete_event(uid, sid), uid)
        assert resp['statusCode'] == 200, resp
        # No league → no leagueUpdate, but the call still succeeds.
        assert json.loads(resp['body']).get('leagueUpdate') is None
