"""Answer checking with fuzzy matching for vocabulary practice."""

import unicodedata
import re
from typing import Tuple


def normalize_answer(text: str) -> str:
    """Normalize an answer for comparison.

    Applies the following transformations:
    1. Strip leading/trailing whitespace
    2. Convert to lowercase
    3. Remove diacritical marks (accents)
    4. Remove common punctuation
    5. Collapse multiple spaces into one

    Args:
        text: The raw answer text

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


def check_answer(user_answer: str, correct_answer: str) -> bool:
    """Check if a user's answer is correct using fuzzy matching.

    The matching rules are:
    1. Exact match after normalization → correct
    2. For words longer than 5 characters: Levenshtein distance ≤ 2 → correct
    3. For words 3-5 characters: Levenshtein distance ≤ 1 → correct
    4. Accept with/without articles as equivalent

    Args:
        user_answer: The user's submitted answer
        correct_answer: The expected correct answer

    Returns:
        True if the answer is considered correct
    """
    if not user_answer or not correct_answer:
        return False

    # Normalize both answers
    norm_user = normalize_answer(user_answer)
    norm_correct = normalize_answer(correct_answer)

    # Exact match after normalization
    if norm_user == norm_correct:
        return True

    # Try matching without articles
    user_no_article = _strip_articles(norm_user)
    correct_no_article = _strip_articles(norm_correct)

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


def _strip_articles(text: str) -> str:
    """Remove common German and French articles from the beginning of text.

    German articles: der, die, das, ein, eine, eines, einem, einen, einer
    French articles: le, la, les, l', un, une, des, du, de la, de l'

    Args:
        text: Normalized text

    Returns:
        Text with leading article removed
    """
    # German articles
    german_articles = [
        'der ', 'die ', 'das ', 'ein ', 'eine ', 'eines ',
        'einem ', 'einen ', 'einer ',
    ]

    # French articles (longer patterns first to avoid partial matches)
    french_articles = [
        'de la ', 'de l ', 'de les ',
        'les ', 'des ', 'une ', 'du ',
        'le ', 'la ', 'un ', 'l ',
    ]

    all_articles = german_articles + french_articles

    for article in all_articles:
        if text.startswith(article):
            return text[len(article):].strip()

    return text


def get_answer_feedback(user_answer: str, correct_answer: str) -> Tuple[bool, str]:
    """Check answer and provide detailed feedback.

    Args:
        user_answer: The user's submitted answer
        correct_answer: The expected correct answer

    Returns:
        Tuple of (is_correct, feedback_message)
    """
    is_correct = check_answer(user_answer, correct_answer)

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
