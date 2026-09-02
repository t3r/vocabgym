"""Answer checking with fuzzy matching for vocabulary practice."""

import unicodedata
import re
from typing import Tuple

from lib.languages import get_all_articles, SOURCE_LANGUAGE


def normalize_answer(text: str, keep_accents: bool = False) -> str:
    """Normalize an answer for comparison.

    Applies the following transformations:
    1. Strip leading/trailing whitespace
    2. Convert to lowercase
    3. Remove diacritical marks (accents) — unless keep_accents is True
    4. Remove common punctuation
    5. Collapse multiple spaces into one

    Args:
        text: The raw answer text
        keep_accents: When True, diacritical marks are preserved (é stays é).
            Case, whitespace, brackets and punctuation are still normalized.
            Used by strict exam grading where accents must match exactly.

    Returns:
        Normalized string for comparison
    """
    if not text:
        return ''

    # Strip whitespace and lowercase
    text = text.strip().lower()

    # Remove anything in square brackets (e.g., phonetic transcription [ynletr])
    text = re.sub(r'\[.*?\]', '', text)

    # Remove anything in parentheses
    text = re.sub(r'\(.*?\)', '', text)

    if keep_accents:
        # Compose so visually-identical accents compare equal (e + ́ === é)
        text = unicodedata.normalize('NFC', text)
    else:
        # Remove diacritical marks (é → e, ç → c, ü → u, etc.)
        text = unicodedata.normalize('NFD', text)
        text = ''.join(
            char for char in text
            if unicodedata.category(char) != 'Mn'
        )

    # Remove common punctuation
    text = re.sub(r'[.,!?;:\'"()\[\]{}]', '', text)

    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein (edit) distance between two strings.

    Uses dynamic programming for O(m*n) time complexity.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Integer edit distance
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def check_answer(user_answer: str, correct_answer: str, target_language: str = 'fr',
                 strict: bool = False) -> bool:
    """Check if a user's answer is correct using fuzzy matching.

    The correct answer may list several acceptable meanings separated by `/` or
    `;` (e.g. "la maison / le logement"). Matching ANY one of them is correct.

    The matching rules for a single option are:
    1. Exact match after normalization → correct
    2. For words longer than 5 characters: Levenshtein distance ≤ 2 → correct
    3. For words 3-5 characters: Levenshtein distance ≤ 1 → correct
    4. Accept with/without articles as equivalent

    Args:
        user_answer: The user's submitted answer
        correct_answer: The expected correct answer
        target_language: Target language code for article stripping (default: 'fr')
        strict: Exam grading. Accents must match exactly (café ≠ cafe) and no
            fuzzy/Levenshtein tolerance is applied. Punctuation/casing are still
            normalized away.

    Returns:
        True if the answer is considered correct
    """
    if not user_answer or not correct_answer:
        return False

    # Split multi-meaning answers ("la maison / le logement"); any match is ok.
    if '/' in correct_answer or ';' in correct_answer:
        options = [o.strip() for o in re.split(r'[;/]', correct_answer) if o.strip()]
        return any(
            _check_single_answer(user_answer, opt, target_language, strict)
            for opt in options
        )

    return _check_single_answer(user_answer, correct_answer, target_language, strict)


def _check_single_answer(user_answer: str, correct_answer: str,
                         target_language: str = 'fr', strict: bool = False) -> bool:
    """Check a user's answer against a single correct option."""
    if not user_answer or not correct_answer:
        return False

    # Strict (exam) grading: accents are significant. Compare with accents kept;
    # punctuation/casing are still ignored. No fuzzy tolerance.
    if strict:
        strict_user = normalize_answer(user_answer, keep_accents=True)
        strict_correct = normalize_answer(correct_answer, keep_accents=True)
        if strict_user and strict_user == strict_correct:
            return True
        # Also accept an exact match ignoring the article ("la maison"/"maison").
        strict_user_na = _strip_articles(strict_user, target_language)
        strict_correct_na = _strip_articles(strict_correct, target_language)
        return bool(strict_user_na) and strict_user_na == strict_correct_na

    # Normalize both answers
    norm_user = normalize_answer(user_answer)
    norm_correct = normalize_answer(correct_answer)

    # Exact match after normalization
    if norm_user == norm_correct:
        return True

    # Try matching without articles
    user_no_article = _strip_articles(norm_user, target_language)
    correct_no_article = _strip_articles(norm_correct, target_language)

    if user_no_article == correct_no_article:
        return True

    # Fuzzy matching with Levenshtein distance
    # Allow more tolerance for longer words
    word_length = max(len(norm_user), len(norm_correct))

    if word_length > 5:
        max_distance = 2
    elif word_length >= 3:
        max_distance = 1
    else:
        max_distance = 0  # Short words must be exact

    distance = levenshtein_distance(norm_user, norm_correct)
    if distance <= max_distance:
        return True

    # Also check without articles with fuzzy matching
    if user_no_article and correct_no_article:
        article_distance = levenshtein_distance(user_no_article, correct_no_article)
        article_length = max(len(user_no_article), len(correct_no_article))

        if article_length > 5 and article_distance <= 2:
            return True
        elif article_length >= 3 and article_distance <= 1:
            return True

    return False


def _strip_articles(text: str, target_language: str = 'fr') -> str:
    """Remove common source and target language articles from the beginning of text.

    Uses the languages module to dynamically build the article list based on
    the source language (German) and the specified target language.

    Args:
        text: Normalized text
        target_language: Target language code (default: 'fr')

    Returns:
        Text with leading article removed
    """
    # Get all articles for both source and target language
    all_articles_list = get_all_articles(target_language)
    if not all_articles_list:
        # Fallback to hardcoded German + French if language not found
        all_articles_list = [
            'der', 'die', 'das', 'ein', 'eine', 'eines', 'einem', 'einen', 'einer',
            'le', 'la', 'les', "l'", 'un', 'une', 'des', 'du', 'de la', "de l'", 'de les',
        ]

    # Sort by length descending to match longer patterns first (e.g., "de la" before "de")
    sorted_articles = sorted(all_articles_list, key=len, reverse=True)

    for article in sorted_articles:
        # Normalize the article for comparison (lowercase)
        norm_article = article.lower()
        # Handle articles that end with apostrophe (e.g., "l'", "de l'")
        if norm_article.endswith("'"):
            if text.startswith(norm_article):
                return text[len(norm_article):].strip()
        else:
            prefix = norm_article + ' '
            if text.startswith(prefix):
                return text[len(prefix):].strip()

    return text


def get_answer_feedback(user_answer: str, correct_answer: str, target_language: str = 'fr') -> Tuple[bool, str]:
    """Check answer and provide detailed feedback.

    Args:
        user_answer: The user's submitted answer
        correct_answer: The expected correct answer
        target_language: Target language code for article stripping (default: 'fr')

    Returns:
        Tuple of (is_correct, feedback_message)
    """
    is_correct = check_answer(user_answer, correct_answer, target_language)

    if is_correct:
        # Check if it was exact or fuzzy
        norm_user = normalize_answer(user_answer)
        norm_correct = normalize_answer(correct_answer)

        if norm_user == norm_correct:
            return True, "Correct!"
        else:
            return True, f"Correct! (accepted: {correct_answer})"
    else:
        return False, f"Incorrect. The correct answer is: {correct_answer}"
