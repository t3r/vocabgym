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
