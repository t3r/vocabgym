"""Comprehensive tests for VocabGym backend — covering bugs found during development.

Covers:
1. HEIC rejection in file upload validation
2. Decimal serialization (DynamoDB Decimal types)
3. Answer checking edge cases (no _strip_phonetics truncation, accent/article/fuzzy)
4. Error pattern detection (article errors vs. completely different answers)
5. Smart repetition (weak words before strong)
6. Language validation (get_language)
7. File validation (extensions, path traversal)
8. Goal status calculation (completed, expired, on_track)
"""

import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# Path setup — must happen before importing application modules
# ---------------------------------------------------------------------------
_test_dir = os.path.dirname(__file__)
_backend_dir = os.path.join(_test_dir, '..')
sys.path.insert(0, os.path.join(_backend_dir, 'layers', 'shared', 'python'))
sys.path.insert(0, os.path.join(_backend_dir, 'functions', 'practice_handler'))
sys.path.insert(0, os.path.join(_backend_dir, 'functions', 'goal_handler'))

# ---------------------------------------------------------------------------
# Environment variables — set BEFORE any boto3 usage
# ---------------------------------------------------------------------------
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
# Remove any real session tokens that would confuse moto
for _key in ('AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN',
             'AWS_CREDENTIAL_EXPIRATION', 'AWS_SESSION_EXPIRATION', 'AWS_PROFILE'):
    os.environ.pop(_key, None)

os.environ.setdefault('IMAGES_BUCKET', 'test-images')
os.environ.setdefault('VOCABSETS_TABLE', 'test-vocabsets')
os.environ.setdefault('VOCABITEMS_TABLE', 'test-vocabitems')
os.environ.setdefault('SESSIONS_TABLE', 'test-sessions')
os.environ.setdefault('PROGRESS_TABLE', 'test-progress')
os.environ.setdefault('LEAGUE_MEMBERS_TABLE', 'test-league-members')
os.environ.setdefault('USERS_TABLE', 'test-users')
os.environ.setdefault('GOALS_TABLE', 'test-goals')
os.environ.setdefault('LEAGUES_TABLE', 'test-leagues')
os.environ.setdefault('REGION', 'eu-central-1')
os.environ.setdefault('ENVIRONMENT', 'test')

# ---------------------------------------------------------------------------
# Imports — pure functions (no module-level AWS clients that call out)
# ---------------------------------------------------------------------------
from lib.utils import DecimalEncoder, build_response
from lib.validation import validate_file_upload, ALLOWED_IMAGE_TYPES
from lib.languages import get_language, get_all_articles
from answer_checker import check_answer, normalize_answer

# For DynamoDB-dependent tests
import boto3
from moto import mock_aws


# ======================================================================
# Shared fixtures for mocked DynamoDB
# ======================================================================

@pytest.fixture()
def mocked_aws():
    """Start moto mock_aws, create tables, yield (ddb, practice_app, goal_app).

    This fixture handles:
    - Starting mock_aws context
    - Creating a fresh boto3 resource inside the mock
    - Creating required DynamoDB tables
    - Monkey-patching the module-level `dynamodb` in practice and goal handlers
    - Restoring everything on teardown
    """
    with mock_aws():
        ddb = boto3.resource('dynamodb', region_name='eu-central-1')

        # Create Progress table
        ddb.create_table(
            TableName=os.environ['PROGRESS_TABLE'],
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

        # Create VocabItems table
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

        # Import both handler modules explicitly by file path to avoid
        # name collision (both are named app.py).
        import importlib.util

        practice_handler_path = os.path.join(_backend_dir, 'functions', 'practice_handler', 'app.py')
        spec_p = importlib.util.spec_from_file_location('practice_handler_app', practice_handler_path)
        practice_app = importlib.util.module_from_spec(spec_p)
        spec_p.loader.exec_module(practice_app)

        goal_handler_path = os.path.join(_backend_dir, 'functions', 'goal_handler', 'app.py')
        spec_g = importlib.util.spec_from_file_location('goal_handler_app', goal_handler_path)
        goal_app = importlib.util.module_from_spec(spec_g)
        spec_g.loader.exec_module(goal_app)

        # Monkey-patch their dynamodb resources
        orig_practice_ddb = practice_app.dynamodb
        orig_goal_ddb = goal_app.dynamodb
        practice_app.dynamodb = ddb
        goal_app.dynamodb = ddb

        yield ddb, practice_app, goal_app

        practice_app.dynamodb = orig_practice_ddb
        goal_app.dynamodb = orig_goal_ddb


# ======================================================================
# 1. HEIC rejection — validate_file_upload must reject image/heic
# ======================================================================

class TestHEICRejection:
    """Bug: HEIC was previously in ALLOWED_IMAGE_TYPES. Now it must be rejected."""

    def test_heic_mime_type_rejected(self):
        valid, err = validate_file_upload('photo.heic', 'image/heic')
        assert valid is False
        assert 'Unsupported file type' in err

    def test_heic_extension_rejected(self):
        valid, err = validate_file_upload('photo.heic', 'image/jpeg')
        assert valid is False
        assert 'Invalid file extension' in err

    def test_heic_not_in_allowed_types(self):
        assert 'image/heic' not in ALLOWED_IMAGE_TYPES

    def test_jpg_still_accepted(self):
        valid, err = validate_file_upload('photo.jpg', 'image/jpeg')
        assert valid is True
        assert err is None

    def test_png_still_accepted(self):
        valid, err = validate_file_upload('photo.png', 'image/png')
        assert valid is True
        assert err is None


# ======================================================================
# 2. Decimal serialization — DynamoDB returns Decimal types
# ======================================================================

class TestDecimalSerialization:
    """Bug: json.dumps crashes on DynamoDB Decimal without custom encoder."""

    def test_decimal_zero(self):
        data = {'count': Decimal('0')}
        result = json.dumps(data, cls=DecimalEncoder)
        assert json.loads(result)['count'] == 0

    def test_decimal_integer(self):
        data = {'score': Decimal('100')}
        result = json.dumps(data, cls=DecimalEncoder)
        assert json.loads(result)['score'] == 100

    def test_decimal_float(self):
        data = {'average': Decimal('3.14')}
        result = json.dumps(data, cls=DecimalEncoder)
        parsed = json.loads(result)['average']
        assert abs(parsed - 3.14) < 0.001

    def test_nested_decimals(self):
        data = {
            'stats': {
                'correct': Decimal('17'),
                'total': Decimal('20'),
                'percentage': Decimal('85.0'),
            }
        }
        result = json.dumps(data, cls=DecimalEncoder)
        parsed = json.loads(result)
        assert parsed['stats']['correct'] == 17
        assert parsed['stats']['total'] == 20

    def test_build_response_handles_decimals(self):
        resp = build_response(200, {'count': Decimal('42')})
        body = json.loads(resp['body'])
        assert body['count'] == 42

    def test_decimal_in_list(self):
        data = {'scores': [Decimal('1'), Decimal('2'), Decimal('3')]}
        result = json.dumps(data, cls=DecimalEncoder)
        parsed = json.loads(result)
        assert parsed['scores'] == [1, 2, 3]


# ======================================================================
# 3. Answer checking edge cases
# ======================================================================

class TestAnswerCheckerEdgeCases:
    """Bugs related to the old _strip_phonetics and fuzzy matching."""

    def test_etw_tauschen_not_truncated(self):
        """normalize_answer must NOT truncate 'etw. tauschen' to 'etw'."""
        result = normalize_answer('etw. tauschen')
        assert 'tauschen' in result
        assert result == 'etw tauschen'

    def test_abbreviation_with_dot_preserved(self):
        result = normalize_answer('qc. faire')
        assert 'faire' in result

    def test_case_insensitive(self):
        assert check_answer('La Maison', 'la maison') is True

    def test_accent_insensitive_cafe(self):
        assert check_answer('cafe', 'café') is True

    def test_accent_insensitive_ecole(self):
        assert check_answer('ecole', 'école') is True

    def test_article_tolerance_french(self):
        assert check_answer('maison', 'la maison') is True

    def test_article_tolerance_german(self):
        assert check_answer('Hund', 'der Hund') is True

    def test_fuzzy_one_char_off(self):
        assert check_answer('la maisom', 'la maison') is True

    def test_completely_different_rejected(self):
        assert check_answer('le chat', 'la maison') is False

    def test_phonetics_brackets_stripped(self):
        result = normalize_answer('un[œ̃] lettre [lɛtʁ]')
        assert 'lettre' in result
        assert '[' not in result

    def test_parentheses_stripped(self):
        result = normalize_answer('faire (qc.)')
        assert result == 'faire'

    def test_empty_answers_return_false(self):
        assert check_answer('', 'la maison') is False
        assert check_answer('test', '') is False
        assert check_answer('', '') is False


# ======================================================================
# 4. Error pattern detection — _analyze_error_patterns
# ======================================================================

class TestErrorPatternDetection:
    """Tests for _analyze_error_patterns from practice_handler/app.py."""

    def test_article_error_detected(self, mocked_aws):
        """User answered 'le maison', correct was 'la maison' → article error."""
        ddb, practice_app, _ = mocked_aws
        wrong_answers = [
            {'userAnswer': 'le maison', 'correctAnswer': 'la maison', 'itemId': 'item-1'}
        ]
        result = practice_app._analyze_error_patterns('user-1', 'vs-1', wrong_answers)
        assert result is not None
        assert 'articleErrors' in result
        assert len(result['articleErrors']) == 1
        assert result['articleErrors'][0]['yourArticle'] == 'le'
        assert result['articleErrors'][0]['correctArticle'] == 'la'
        assert 'Artikel-Fehler' in result['summary']

    def test_not_article_error_when_different_word(self, mocked_aws):
        """User answered 'le chat', correct was 'la maison' → NOT article error."""
        ddb, practice_app, _ = mocked_aws
        wrong_answers = [
            {'userAnswer': 'le chat', 'correctAnswer': 'la maison', 'itemId': 'item-2'}
        ]
        result = practice_app._analyze_error_patterns('user-1', 'vs-1', wrong_answers)
        assert result is None or 'articleErrors' not in result

    def test_repeated_error_detected(self, mocked_aws):
        """An item with >=2 recentErrors should be flagged as repeated error."""
        ddb, practice_app, _ = mocked_aws
        table = ddb.Table(os.environ['PROGRESS_TABLE'])
        table.put_item(Item={
            'progressKey': 'user-1#vs-1',
            'itemId': 'item-3',
            'incorrectCount': 5,
            'correctCount': 2,
            'masteryLevel': 1,
            'recentErrors': [
                {'answer': 'le ecole', 'timestamp': 1000},
                {'answer': 'lecole', 'timestamp': 2000},
                {'answer': "l'ecole", 'timestamp': 3000},
            ],
        })
        wrong_answers = [
            {'userAnswer': "l'ecole", 'correctAnswer': "l'école", 'itemId': 'item-3'}
        ]
        result = practice_app._analyze_error_patterns('user-1', 'vs-1', wrong_answers)
        assert result is not None
        assert 'repeatedErrors' in result
        assert len(result['repeatedErrors']) >= 1
        assert result['repeatedErrors'][0]['timesWrong'] == 5

    def test_article_error_german(self, mocked_aws):
        """'der Haus' instead of 'das Haus' → article error."""
        ddb, practice_app, _ = mocked_aws
        wrong_answers = [
            {'userAnswer': 'der Haus', 'correctAnswer': 'das Haus', 'itemId': 'item-4'}
        ]
        result = practice_app._analyze_error_patterns('user-1', 'vs-1', wrong_answers)
        assert result is not None
        assert 'articleErrors' in result
        assert result['articleErrors'][0]['yourArticle'] == 'der'
        assert result['articleErrors'][0]['correctArticle'] == 'das'


# ======================================================================
# 5. Smart repetition — _prioritize_items
# ======================================================================

class TestSmartRepetition:
    """_prioritize_items should put weak words before strong ones."""

    def _seed_progress(self, ddb):
        """Seed progress data for strong and weak items."""
        table = ddb.Table(os.environ['PROGRESS_TABLE'])
        pk = 'user-1#vs-1'
        table.put_item(Item={
            'progressKey': pk, 'itemId': 'strong-item',
            'masteryLevel': 5, 'correctCount': 20, 'incorrectCount': 0,
            'consecutiveCorrect': 10, 'recentErrors': [],
        })
        table.put_item(Item={
            'progressKey': pk, 'itemId': 'weak-item',
            'masteryLevel': 0, 'correctCount': 1, 'incorrectCount': 8,
            'consecutiveCorrect': 0,
            'recentErrors': [
                {'answer': 'wrong1', 'timestamp': 1000},
                {'answer': 'wrong2', 'timestamp': 2000},
                {'answer': 'wrong3', 'timestamp': 3000},
            ],
        })

    def test_weak_before_strong(self, mocked_aws):
        ddb, practice_app, _ = mocked_aws
        self._seed_progress(ddb)
        items = [
            {'itemId': 'strong-item', 'source': 'das Haus', 'target': 'la maison'},
            {'itemId': 'weak-item', 'source': 'die Schule', 'target': "l'école"},
        ]
        weak_first = sum(
            1 for _ in range(50)
            if practice_app._prioritize_items(list(items), 'user-1', 'vs-1')[0]['itemId'] == 'weak-item'
        )
        assert weak_first > 35, f"Weak item first only {weak_first}/50 times"

    def test_new_item_before_strong(self, mocked_aws):
        ddb, practice_app, _ = mocked_aws
        self._seed_progress(ddb)
        items = [
            {'itemId': 'strong-item', 'source': 'das Haus', 'target': 'la maison'},
            {'itemId': 'new-item', 'source': 'der Tisch', 'target': 'la table'},
            {'itemId': 'weak-item', 'source': 'die Schule', 'target': "l'école"},
        ]
        new_before_strong = 0
        for _ in range(50):
            ids = [p['itemId'] for p in practice_app._prioritize_items(list(items), 'user-1', 'vs-1')]
            if ids.index('new-item') < ids.index('strong-item'):
                new_before_strong += 1
        assert new_before_strong > 35, f"New before strong only {new_before_strong}/50 times"


# ======================================================================
# 6. Language validation
# ======================================================================

class TestLanguageValidation:

    def test_french(self):
        lang = get_language('fr')
        assert lang is not None
        assert lang['code'] == 'fr'
        assert lang['name'] == 'Französisch'

    def test_english(self):
        assert get_language('en') is not None

    def test_spanish(self):
        assert get_language('es') is not None

    def test_italian(self):
        assert get_language('it') is not None

    def test_unknown_returns_none(self):
        assert get_language('xx') is None
        assert get_language('') is None
        assert get_language('de') is None

    def test_get_all_articles_french(self):
        arts = get_all_articles('fr')
        assert arts is not None
        assert 'le' in arts and 'la' in arts and 'der' in arts

    def test_get_all_articles_unknown(self):
        assert get_all_articles('xx') is None


# ======================================================================
# 7. File validation
# ======================================================================

class TestFileValidation:

    def test_accept_jpg(self):
        assert validate_file_upload('photo.jpg', 'image/jpeg') == (True, None)

    def test_accept_jpeg(self):
        assert validate_file_upload('photo.jpeg', 'image/jpeg') == (True, None)

    def test_accept_png(self):
        assert validate_file_upload('photo.png', 'image/png') == (True, None)

    def test_reject_heic(self):
        v, _ = validate_file_upload('photo.heic', 'image/heic')
        assert v is False

    def test_reject_gif(self):
        v, _ = validate_file_upload('anim.gif', 'image/gif')
        assert v is False

    def test_reject_pdf(self):
        v, _ = validate_file_upload('doc.pdf', 'application/pdf')
        assert v is False

    def test_reject_path_traversal_dotdot(self):
        v, err = validate_file_upload('../etc/passwd.jpg', 'image/jpeg')
        assert v is False and 'Invalid characters' in err

    def test_reject_path_traversal_slash(self):
        v, err = validate_file_upload('/etc/shadow.jpg', 'image/jpeg')
        assert v is False and 'Invalid characters' in err

    def test_reject_path_traversal_backslash(self):
        v, err = validate_file_upload('..\\photo.jpg', 'image/jpeg')
        assert v is False and 'Invalid characters' in err

    def test_reject_no_extension(self):
        v, _ = validate_file_upload('photo', 'image/jpeg')
        assert v is False

    def test_reject_empty_filename(self):
        v, _ = validate_file_upload('', 'image/jpeg')
        assert v is False

    def test_reject_empty_content_type(self):
        v, _ = validate_file_upload('photo.jpg', '')
        assert v is False


# ======================================================================
# 8. Goal status calculation
# ======================================================================

class TestGoalStatusCalculation:

    def _seed(self, ddb, vs_id, user_id, total, mastered, target_mastery=4):
        it = ddb.Table(os.environ['VOCABITEMS_TABLE'])
        pt = ddb.Table(os.environ['PROGRESS_TABLE'])
        pk = f"{user_id}#{vs_id}"
        for i in range(total):
            iid = f"item-{vs_id}-{i}"
            it.put_item(Item={'vocabSetId': vs_id, 'itemId': iid, 'source': f'w{i}', 'target': f'm{i}', 'isActive': True})
            ml = target_mastery if i < mastered else 1
            pt.put_item(Item={'progressKey': pk, 'itemId': iid, 'masteryLevel': ml, 'correctCount': 10 if i < mastered else 2, 'incorrectCount': 0 if i < mastered else 3})

    def test_completed(self, mocked_aws):
        ddb, _, goal_app = mocked_aws
        self._seed(ddb, 'vs-c', 'u1', 10, 10)
        g = {'vocabSetIds': ['vs-c'], 'deadline': (date.today() + timedelta(days=7)).isoformat(), 'targetMastery': 4, 'createdAt': (date.today() - timedelta(days=3)).isoformat()}
        s = goal_app.calculate_goal_status(g, 'u1')
        assert s['status'] == 'completed'
        assert s['progressPercent'] == 100.0

    def test_expired(self, mocked_aws):
        ddb, _, goal_app = mocked_aws
        self._seed(ddb, 'vs-e', 'u2', 10, 3)
        g = {'vocabSetIds': ['vs-e'], 'deadline': (date.today() - timedelta(days=1)).isoformat(), 'targetMastery': 4, 'createdAt': (date.today() - timedelta(days=14)).isoformat()}
        s = goal_app.calculate_goal_status(g, 'u2')
        assert s['status'] == 'expired'
        assert s['progressPercent'] == 30.0

    def test_on_track(self, mocked_aws):
        ddb, _, goal_app = mocked_aws
        self._seed(ddb, 'vs-t', 'u3', 10, 7)
        g = {'vocabSetIds': ['vs-t'], 'deadline': (date.today() + timedelta(days=7)).isoformat(), 'targetMastery': 4, 'createdAt': (date.today() - timedelta(days=7)).isoformat()}
        s = goal_app.calculate_goal_status(g, 'u3')
        assert s['status'] == 'on_track'
        assert s['progressPercent'] == 70.0

    def test_behind(self, mocked_aws):
        ddb, _, goal_app = mocked_aws
        self._seed(ddb, 'vs-b', 'u4', 20, 1)
        g = {'vocabSetIds': ['vs-b'], 'deadline': (date.today() + timedelta(days=2)).isoformat(), 'targetMastery': 4, 'createdAt': (date.today() - timedelta(days=10)).isoformat()}
        s = goal_app.calculate_goal_status(g, 'u4')
        assert s['status'] in ('behind', 'at_risk')
        assert s['progressPercent'] == 5.0

    def test_empty_vocab_set(self, mocked_aws):
        _, _, goal_app = mocked_aws
        g = {'vocabSetIds': ['nonexistent'], 'deadline': (date.today() + timedelta(days=7)).isoformat(), 'targetMastery': 4, 'createdAt': date.today().isoformat()}
        s = goal_app.calculate_goal_status(g, 'u-empty')
        assert s['totalWords'] == 0
        assert s['progressPercent'] == 0.0

    def test_multiple_sets(self, mocked_aws):
        ddb, _, goal_app = mocked_aws
        self._seed(ddb, 'vs-a', 'u5', 10, 10)
        self._seed(ddb, 'vs-b', 'u5', 10, 0)
        g = {'vocabSetIds': ['vs-a', 'vs-b'], 'deadline': (date.today() + timedelta(days=7)).isoformat(), 'targetMastery': 4, 'createdAt': (date.today() - timedelta(days=3)).isoformat()}
        s = goal_app.calculate_goal_status(g, 'u5')
        assert s['totalWords'] == 20
        assert s['masteredWords'] == 10
        assert s['progressPercent'] == 50.0
