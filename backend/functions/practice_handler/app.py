"""Practice Handler - Manage practice sessions with answer validation."""

import datetime
import json
import logging
import math
import os
import random

import boto3
from boto3.dynamodb.conditions import Key

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    generate_uuid,
    get_timestamp,
    parse_body,
)
from lib.validation import validate_practice_options, validate_uuid

from answer_checker import check_answer, normalize_answer

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
VOCABSETS_TABLE = os.environ.get('VOCABSETS_TABLE', '')
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
SESSIONS_TABLE = os.environ['SESSIONS_TABLE']
PROGRESS_TABLE = os.environ['PROGRESS_TABLE']
LEAGUES_TABLE = os.environ.get('LEAGUES_TABLE', '')
LEAGUE_MEMBERS_TABLE = os.environ.get('LEAGUE_MEMBERS_TABLE', '')
USERS_TABLE = os.environ.get('USERS_TABLE', '')

# TTL: 90 days for practice sessions
SESSION_TTL_DAYS = 90

# Smart Repetition defaults
DEFAULT_SESSION_LENGTH = 20   # questions per session when client doesn't specify
MAX_REPEATS_PER_ITEM = 3      # max times one word can appear in a single session


def lambda_handler(event, context):
    """Route practice requests.

    Routes:
    - POST /practice/start: Start a new practice session
    - POST /practice/submit: Submit an answer for the current question
    - POST /practice/complete: Complete a practice session
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(json.dumps({
        'event': 'practice_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        if http_method == 'POST' and '/start' in path:
            return handle_start(event, user_id)
        elif http_method == 'POST' and '/submit' in path:
            return handle_submit(event, user_id)
        elif http_method == 'POST' and '/complete' in path:
            return handle_complete(event, user_id)
        else:
            return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in practice handler: {e}")
        return build_error_response(e, 'practice_handler')


def handle_start(event, user_id):
    """Handle POST /practice/start - Start a new practice session.

    Expected body:
    {
        "vocabSetId": "uuid",
        "direction": "de-fr" or "fr-de",
        "questionCount": 20  (optional)
    }
    """
    body = parse_body(event)

    is_valid, err = validate_practice_options(body)
    if not is_valid:
        return build_response(400, {'error': err})

    vocab_set_id = body['vocabSetId']
    direction = body.get('direction', 'de-fr')
    question_count = int(body.get('questionCount', 0)) or None

    # Practice mode: 'practice' (default) or 'exam' (timed, no hints).
    mode = body.get('mode', 'practice')
    if mode not in ('practice', 'exam'):
        mode = 'practice'

    # Map old direction values to new ones internally
    direction_map = {
        'de-fr': 'source-target',
        'fr-de': 'target-source',
        'source-target': 'source-target',
        'target-source': 'target-source',
    }
    internal_direction = direction_map.get(direction, 'source-target')

    # SECURITY: Verify ownership or league assignment before accessing vocab items.
    # This prevents IDOR attacks where any user could practice another user's
    # private vocabulary sets by guessing/enumerating vocabSetIds.
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    vocab_set_resp = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )
    vocab_set = vocab_set_resp.get('Item')

    if not vocab_set:
        # Not owned by caller. Check if it's a league-assigned set.
        # Resolution is deterministic: fetch caller's league, verify the set is
        # assigned, then fetch by the known teacher owner (no cross-owner scan).
        users_table = dynamodb.Table(USERS_TABLE)
        user = users_table.get_item(Key={'userId': user_id}).get('Item', {})
        league_id = user.get('leagueId')

        if not league_id:
            # Not owned, no league → uniform 404 (never 403, prevents existence probes)
            return build_response(404, {'error': 'Vocabulary set not found'})

        leagues_table = dynamodb.Table(LEAGUES_TABLE)
        league = leagues_table.get_item(Key={'leagueId': league_id}).get('Item', {})
        assigned_ids = league.get('vocabSetIds', [])
        teacher_user_id = league.get('teacherUserId')

        if vocab_set_id not in assigned_ids or not teacher_user_id:
            return build_response(404, {'error': 'Vocabulary set not found'})

        # Deterministic fetch by known teacher owner
        vocab_set_resp = vocabsets_table.get_item(
            Key={'vocabSetId': vocab_set_id, 'userId': teacher_user_id}
        )
        vocab_set = vocab_set_resp.get('Item')
        if not vocab_set:
            return build_response(404, {'error': 'Vocabulary set not found'})

    # Fetch vocabulary items (now authorized)
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    response = items_table.query(
        KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
    )

    items = response.get('Items', [])
    if not items:
        return build_response(404, {'error': 'No vocabulary items found for this set'})

    # Filter only active items
    active_items = [item for item in items if item.get('isActive', True)]
    if not active_items:
        return build_response(404, {'error': 'No active vocabulary items found'})

    # Smart Repetition: build the session by WEIGHTED SELECTION (not just
    # ordering). Weak words are far more likely and may appear multiple times in
    # one session; mastered words are strongly under-weighted but never fully
    # excluded, so they still get occasional refreshes (avoid forgetting).
    session_length = question_count or min(DEFAULT_SESSION_LENGTH, len(active_items))
    selected_items = _select_items_weighted(active_items, user_id, vocab_set_id, session_length)

    # Load progress to flag words that were never answered correctly ("new"),
    # so the client can offer the solution/pronunciation immediately.
    correct_by_item = _get_correct_counts(user_id, vocab_set_id)

    # Create session
    session_id = generate_uuid()
    timestamp = get_timestamp()
    expires_at = timestamp + (SESSION_TTL_DAYS * 24 * 60 * 60)

    # Build questions
    questions = []
    for i, item in enumerate(selected_items):
        question_id = generate_uuid()
        source_text = item.get('source', item.get('german', ''))
        target_text = item.get('target', item.get('french', ''))

        if internal_direction == 'source-target':
            question_text = source_text
            correct_answer = target_text
        else:
            question_text = target_text
            correct_answer = source_text

        questions.append({
            'questionId': question_id,
            'itemId': item['itemId'],
            'source': source_text,
            'target': target_text,
            'question': question_text,
            'correctAnswer': correct_answer,
            'questionNumber': i + 1,
            'isNew': int(correct_by_item.get(item['itemId'], 0)) == 0,
            'notes': item.get('notes', ''),
        })

    # Store session in DynamoDB
    sessions_table = dynamodb.Table(SESSIONS_TABLE)
    sessions_table.put_item(
        Item={
            'userId': user_id,
            'sessionId': session_id,
            'vocabSetId': vocab_set_id,
            'direction': direction,
            'mode': mode,
            'totalQuestions': len(questions),
            'correctAnswers': 0,
            'startedAt': timestamp,
            'completedAt': 0,
            'duration': 0,
            'status': 'active',
            'questions': questions,
            'detailedResults': [],
            'expiresAt': expires_at,
        }
    )

    logger.info(json.dumps({
        'event': 'practice_started',
        'sessionId': session_id,
        'userId': user_id,
        'vocabSetId': vocab_set_id,
        'questionCount': len(questions),
        'direction': direction,
    }))

    # Return questions with answers (client-side checking for instant feedback)
    return build_response(200, {
        'sessionId': session_id,
        'vocabSetId': vocab_set_id,
        'direction': direction,
        'mode': mode,
        'totalQuestions': len(questions),
        'questions': [
            {
                'questionId': q['questionId'],
                'itemId': q['itemId'],
                'question': q['question'],
                'correctAnswer': q['correctAnswer'],
                'questionNumber': q['questionNumber'],
                'totalQuestions': len(questions),
                'isNew': q['isNew'],
            }
            for q in questions
        ],
    })


def handle_submit(event, user_id):
    """Handle POST /practice/submit - Submit an answer and get feedback.

    Expected body:
    {
        "sessionId": "uuid",
        "questionId": "uuid",
        "answer": "la maison"
    }
    """
    body = parse_body(event)

    session_id = body.get('sessionId')
    question_id = body.get('questionId')
    user_answer = body.get('answer', '').strip()

    if not session_id or not question_id:
        return build_response(400, {'error': 'sessionId and questionId are required'})

    if not user_answer:
        return build_response(400, {'error': 'Answer is required'})

    # Get session
    sessions_table = dynamodb.Table(SESSIONS_TABLE)
    response = sessions_table.get_item(
        Key={'userId': user_id, 'sessionId': session_id}
    )

    session = response.get('Item')
    if not session:
        return build_response(404, {'error': 'Practice session not found'})

    if session.get('status') == 'completed':
        return build_response(400, {'error': 'This session is already completed'})

    # Find the question
    questions = session.get('questions', [])
    question = None
    for q in questions:
        if q['questionId'] == question_id:
            question = q
            break

    if not question:
        return build_response(404, {'error': 'Question not found in this session'})

    correct_answer = question['correctAnswer']

    # Check answer using fuzzy matching
    is_correct = check_answer(user_answer, correct_answer)

    # Record result
    result = {
        'questionId': question_id,
        'itemId': question['itemId'],
        'question': question['question'],
        'correctAnswer': correct_answer,
        'userAnswer': user_answer,
        'correct': is_correct,
        'answeredAt': get_timestamp(),
    }

    # Update session with result
    detailed_results = session.get('detailedResults', [])
    detailed_results.append(result)
    correct_count = sum(1 for r in detailed_results if r['correct'])

    sessions_table.update_item(
        Key={'userId': user_id, 'sessionId': session_id},
        UpdateExpression='SET detailedResults = :results, correctAnswers = :correct',
        ExpressionAttributeValues={
            ':results': detailed_results,
            ':correct': correct_count,
        }
    )

    # Update progress for this item
    _update_item_progress(user_id, session['vocabSetId'], question['itemId'], is_correct, user_answer=user_answer)

    logger.info(json.dumps({
        'event': 'answer_submitted',
        'sessionId': session_id,
        'questionId': question_id,
        'correct': is_correct,
    }))

    return build_response(200, {
        'correct': is_correct,
        'correctAnswer': correct_answer,
        'userAnswer': user_answer,
        'questionsAnswered': len(detailed_results),
        'totalQuestions': session['totalQuestions'],
    })


def handle_complete(event, user_id):
    """Handle POST /practice/complete - Complete a practice session.

    Expected body:
    {
        "sessionId": "uuid"
    }
    """
    body = parse_body(event)
    session_id = body.get('sessionId')

    if not session_id:
        return build_response(400, {'error': 'sessionId is required'})

    # Get session
    sessions_table = dynamodb.Table(SESSIONS_TABLE)
    response = sessions_table.get_item(
        Key={'userId': user_id, 'sessionId': session_id}
    )

    session = response.get('Item')
    if not session:
        return build_response(404, {'error': 'Practice session not found'})

    if session.get('status') == 'completed':
        return build_response(400, {'error': 'Session is already completed'})

    # Get results from request body (client-side answer checking)
    client_results = body.get('results', [])

    # Fall back to results already persisted during the session via
    # /practice/submit. This prevents an empty or partial complete request
    # (e.g. session abandoned, double-complete, client state reset) from
    # wiping out good data with 0/total.
    stored_results = session.get('detailedResults', []) or []
    if not client_results and stored_results:
        logger.info(json.dumps({
            'event': 'complete_using_stored_results',
            'sessionId': session_id,
            'storedCount': len(stored_results),
        }))
        client_results = stored_results

    # Calculate statistics
    timestamp = get_timestamp()
    started_at = session.get('startedAt', timestamp)
    duration = timestamp - started_at
    correct_count = sum(1 for r in client_results if r.get('correct'))
    total = len(client_results) if client_results else int(session.get('totalQuestions', 0))
    score = int((correct_count / total * 100) if total > 0 else 0)

    # Guard: never overwrite the session's existing results/score with an
    # empty set. If there are no results to record (neither from the request
    # nor previously stored), just mark the session completed without
    # clobbering correctAnswers/score/detailedResults.
    if not client_results:
        logger.warning(json.dumps({
            'event': 'complete_without_results',
            'sessionId': session_id,
            'userId': user_id,
        }))
        sessions_table.update_item(
            Key={'userId': user_id, 'sessionId': session_id},
            UpdateExpression=(
                'SET #status = :status, completedAt = :completedAt, '
                '#duration = :duration'
            ),
            ExpressionAttributeNames={'#status': 'status', '#duration': 'duration'},
            ExpressionAttributeValues={
                ':status': 'completed',
                ':completedAt': timestamp,
                ':duration': duration,
            }
        )
        return build_response(200, {
            'sessionId': session_id,
            'score': int(session.get('score', 0)),
            'correct': int(session.get('correctAnswers', 0)),
            'total': int(session.get('totalQuestions', 0)),
            'duration': duration,
            'mode': session.get('mode', 'practice'),
            'detailedResults': stored_results,
        })

    # Update session
    sessions_table.update_item(
        Key={'userId': user_id, 'sessionId': session_id},
        UpdateExpression=(
            'SET #status = :status, completedAt = :completedAt, '
            '#duration = :duration, correctAnswers = :correct, score = :score, '
            'totalQuestions = :total, detailedResults = :results'
        ),
        ExpressionAttributeNames={'#status': 'status', '#duration': 'duration'},
        ExpressionAttributeValues={
            ':status': 'completed',
            ':completedAt': timestamp,
            ':duration': duration,
            ':correct': correct_count,
            ':score': score,
            ':total': total,
            ':results': client_results,
        }
    )

    # Update progress for each answered item
    vocab_set_id = session.get('vocabSetId', '')
    for result in client_results:
        item_id = result.get('itemId')
        if item_id:
            _update_item_progress(
                user_id, vocab_set_id, item_id,
                result.get('correct', False),
                user_answer=result.get('userAnswer')
            )

    logger.info(json.dumps({
        'event': 'practice_completed',
        'sessionId': session_id,
        'userId': user_id,
        'score': score,
        'correct': correct_count,
        'total': total,
        'duration': duration,
    }, default=str))

    # League score + streak update
    league_update = None
    if LEAGUE_MEMBERS_TABLE and USERS_TABLE:
        league_update = _update_league_stats(user_id, correct_count, total)

    response_body = {
        'sessionId': session_id,
        'score': score,
        'correct': correct_count,
        'total': total,
        'duration': duration,
        'mode': session.get('mode', 'practice'),
        'detailedResults': client_results,
    }
    if league_update:
        response_body['leagueUpdate'] = league_update

    # Analyze error patterns for this session
    wrong_answers = [r for r in client_results if not r.get('correct', False)]
    if wrong_answers:
        patterns = _analyze_error_patterns(user_id, vocab_set_id, wrong_answers)
        if patterns:
            response_body['errorPatterns'] = patterns

    return build_response(200, response_body)


def _analyze_error_patterns(user_id, vocab_set_id, wrong_answers):
    """Analyze error patterns from this session and historical data.

    Detects:
    - Article/gender errors (wrong article, correct word)
    - Repeated mistakes on same words
    - Common confusion patterns

    Args:
        user_id: User ID
        vocab_set_id: Vocabulary set ID
        wrong_answers: List of wrong answer dicts from this session

    Returns:
        dict with pattern analysis or None if no patterns detected
    """
    patterns = {
        'articleErrors': [],    # Words where only the article was wrong
        'repeatedErrors': [],   # Words that were wrong before (from recentErrors)
        'confusions': [],       # Words confused with each other
        'summary': '',          # German text summary of findings
    }

    # Load historical progress for this user+set
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    progress_key = f"{user_id}#{vocab_set_id}"

    try:
        progress_response = progress_table.query(
            KeyConditionExpression=Key('progressKey').eq(progress_key)
        )
        progress_items = {
            p['itemId']: p for p in progress_response.get('Items', [])
        }
    except Exception:
        progress_items = {}

    # German and common target language articles for detection
    all_articles = [
        'der', 'die', 'das', 'ein', 'eine',
        'le', 'la', 'les', 'un', 'une', 'des', "l'",
        'el', 'la', 'los', 'las',
        'il', 'lo', 'i', 'gli',
        'the', 'a', 'an',
    ]

    for wrong in wrong_answers:
        user_answer = (wrong.get('userAnswer') or '').strip().lower()
        correct_answer = (wrong.get('correctAnswer') or '').strip().lower()
        item_id = wrong.get('itemId', '')

        if not user_answer or not correct_answer:
            continue

        # Detect article errors: same word, different article
        user_parts = user_answer.split(' ', 1)
        correct_parts = correct_answer.split(' ', 1)

        if (len(user_parts) > 1 and len(correct_parts) > 1
                and user_parts[0] in all_articles and correct_parts[0] in all_articles
                and user_parts[1] == correct_parts[1]):
            patterns['articleErrors'].append({
                'word': correct_answer,
                'yourArticle': user_parts[0],
                'correctArticle': correct_parts[0],
            })
            continue

        # Detect repeated errors (same word wrong multiple times historically)
        progress = progress_items.get(item_id, {})
        recent_errors = progress.get('recentErrors', [])
        if len(recent_errors) >= 2:
            patterns['repeatedErrors'].append({
                'word': correct_answer,
                'timesWrong': int(progress.get('incorrectCount', 0)),
                'lastAnswers': [e.get('answer', '') for e in recent_errors[-3:]],
            })

    # Build summary text
    summary_parts = []
    if patterns['articleErrors']:
        count = len(patterns['articleErrors'])
        summary_parts.append(
            f"Artikel-Fehler bei {count} {'Wort' if count == 1 else 'Wörtern'} "
            f"— achte auf das grammatische Geschlecht!"
        )
    if patterns['repeatedErrors']:
        count = len(patterns['repeatedErrors'])
        words = ', '.join(e['word'] for e in patterns['repeatedErrors'][:3])
        summary_parts.append(
            f"{count} Wörter bereiten dir wiederholt Schwierigkeiten: {words}"
        )

    if not summary_parts:
        return None

    patterns['summary'] = ' '.join(summary_parts)

    # Remove empty lists from response
    patterns = {k: v for k, v in patterns.items() if v}

    return patterns


def _get_correct_counts(user_id, vocab_set_id):
    """Return a map {itemId: correctCount} for the user's progress in a set.

    Used to flag "new" words (correctCount == 0 → never answered correctly).
    """
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    progress_key = f"{user_id}#{vocab_set_id}"
    try:
        resp = progress_table.query(
            KeyConditionExpression=Key('progressKey').eq(progress_key)
        )
        return {
            p['itemId']: int(p.get('correctCount', 0))
            for p in resp.get('Items', [])
        }
    except Exception as e:
        logger.warning(f"Failed to fetch correct counts: {e}")
        return {}


def _select_items_weighted(active_items, user_id, vocab_set_id, count):
    """Select *count* questions via weighted random draw (with replacement).

    Unlike the old _prioritize_items which only sorted all items:
    - Weak/error-prone words are drawn FAR more often and may appear multiple
      times per session (capped at MAX_REPEATS_PER_ITEM).
    - Mastered words (mastery 5, high consecutive-correct) get a very low weight
      but are never fully excluded, so they receive occasional refreshes.
    - The result is a list of *count* items (possibly shorter if the pool is
      tiny) that genuinely reflects the 'practise weakness more' design intent.

    Weight formula (roughly):
      w = (6 - mastery)² + recent_error_boost + error_rate_boost
      … clamped to a minimum of 0.3 so mastered words still have a non-zero
      chance.
    """
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    progress_key = f"{user_id}#{vocab_set_id}"

    try:
        progress_response = progress_table.query(
            KeyConditionExpression=Key('progressKey').eq(progress_key)
        )
        progress_items = {
            p['itemId']: p for p in progress_response.get('Items', [])
        }
    except Exception as e:
        logger.warning(f"Failed to fetch progress for weighted selection: {e}")
        random.shuffle(active_items)
        return active_items[:count]

    # --- Compute weight per item -----------------------------------------
    item_weights = []
    for item in active_items:
        progress = progress_items.get(item['itemId'], {})

        mastery = int(progress.get('masteryLevel', 0))
        consecutive_correct = int(progress.get('consecutiveCorrect', 0))
        incorrect_count = int(progress.get('incorrectCount', 0))
        correct_count = int(progress.get('correctCount', 0))
        recent_errors = progress.get('recentErrors', [])

        if correct_count == 0 and incorrect_count == 0:
            # Never practised — high weight to introduce early
            weight = 20.0
        else:
            # Base: square of inverse mastery → big gap between weak and strong
            weight = (6 - mastery) ** 2  # mastery 0→36, 3→9, 5→1

            # Boost for recent errors (up to +12)
            weight += min(len(recent_errors), 3) * 4.0

            # Boost for overall error rate (up to +8)
            total = correct_count + incorrect_count
            if total > 0:
                weight += (incorrect_count / total) * 8.0

            # Penalise long streaks of correct answers
            weight -= min(consecutive_correct, 5) * 1.5

        # Floor: mastered words still get a non-zero chance (refreshes)
        weight = max(weight, 0.3)
        item_weights.append((item, weight))

    # --- Weighted draw with capped repetitions ---------------------------
    total_weight = sum(w for _, w in item_weights)
    probabilities = [w / total_weight for _, w in item_weights]

    # Repeat cap scales with pool size: for small sets a word must be allowed to
    # repeat more often to both fill the session AND preserve the weak/strong
    # imbalance. e.g. 2 words / 10 questions → cap high enough to let the weak
    # word dominate; large sets keep the small default.
    pool_size = len(item_weights)
    repeat_cap = max(MAX_REPEATS_PER_ITEM, math.ceil(count / max(pool_size, 1)) + 1)

    selected = []
    repeat_counts = {}  # itemId → how often already drawn

    for _ in range(count):
        # Build a filtered probability list (exclude maxed-out items)
        filtered = []
        filt_probs = []
        for idx, (item, _w) in enumerate(item_weights):
            iid = item['itemId']
            if repeat_counts.get(iid, 0) >= repeat_cap:
                continue
            filtered.append(idx)
            filt_probs.append(probabilities[idx])

        if not filtered:
            break  # all items maxed out (tiny set, long session)

        # Normalise after filtering
        psum = sum(filt_probs)
        filt_probs = [p / psum for p in filt_probs]

        # Weighted random choice
        r = random.random()
        cumulative = 0.0
        chosen_idx = filtered[0]
        for fi, fp in zip(filtered, filt_probs):
            cumulative += fp
            if r <= cumulative:
                chosen_idx = fi
                break

        chosen_item = item_weights[chosen_idx][0]
        selected.append(chosen_item)
        repeat_counts[chosen_item['itemId']] = repeat_counts.get(chosen_item['itemId'], 0) + 1

    # --- Spread repeats: avoid the same word twice in a row ---------------
    _spread_repeats(selected)

    return selected


def _spread_repeats(items):
    """Reorder items in-place so the same itemId doesn't appear consecutively.

    Simple greedy swap: whenever item[i] == item[i-1], find the nearest
    different item ahead and swap.  Best-effort — if the session is very short
    and dominated by one word, some consecutive repeats may remain.
    """
    for i in range(1, len(items)):
        if items[i]['itemId'] == items[i - 1]['itemId']:
            # Find closest different item to swap with
            for j in range(i + 1, len(items)):
                if items[j]['itemId'] != items[i - 1]['itemId']:
                    items[i], items[j] = items[j], items[i]
                    break


def _update_item_progress(user_id, vocab_set_id, item_id, is_correct, user_answer=None):
    """Update the progress table for a specific vocabulary item.

    Args:
        user_id: User ID
        vocab_set_id: Vocabulary set ID
        item_id: Vocabulary item ID
        is_correct: Whether the answer was correct
        user_answer: The user's answer (stored on errors for pattern detection)
    """
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    progress_key = f"{user_id}#{vocab_set_id}"
    timestamp = get_timestamp()

    try:
        # Step 1: Atomic update of counters
        if is_correct:
            update_expr = (
                'SET correctCount = if_not_exists(correctCount, :zero) + :one, '
                'lastPracticedAt = :ts, '
                'consecutiveCorrect = if_not_exists(consecutiveCorrect, :zero) + :one'
            )
            expr_values = {':one': 1, ':zero': 0, ':ts': timestamp}
        else:
            error_entry = {'answer': user_answer or '', 'timestamp': timestamp}
            update_expr = (
                'SET incorrectCount = if_not_exists(incorrectCount, :zero) + :one, '
                'lastPracticedAt = :ts, '
                'consecutiveCorrect = :zero, '
                'recentErrors = list_append(if_not_exists(recentErrors, :empty), :newError)'
            )
            expr_values = {':one': 1, ':zero': 0, ':ts': timestamp, ':empty': [], ':newError': [error_entry]}

        progress_table.update_item(
            Key={'progressKey': progress_key, 'itemId': item_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )

        # Step 2: Single read, then compute mastery + trim errors in one write
        response = progress_table.get_item(
            Key={'progressKey': progress_key, 'itemId': item_id}
        )
        item = response.get('Item', {})
        correct = int(item.get('correctCount', 0))
        incorrect = int(item.get('incorrectCount', 0))
        total_attempts = correct + incorrect
        mastery = min(5, int((correct / total_attempts) * 5)) if total_attempts > 0 else 0

        # Build single update for mastery + trimmed errors + userId/vocabSetId
        update_parts = ['masteryLevel = :mastery', 'userId = :uid', 'vocabSetId = :vsid']
        final_values = {':mastery': mastery, ':uid': user_id, ':vsid': vocab_set_id}

        recent_errors = item.get('recentErrors', [])
        if len(recent_errors) > 5:
            update_parts.append('recentErrors = :trimmed')
            final_values[':trimmed'] = recent_errors[-5:]

        progress_table.update_item(
            Key={'progressKey': progress_key, 'itemId': item_id},
            UpdateExpression='SET ' + ', '.join(update_parts),
            ExpressionAttributeValues=final_values,
        )

    except Exception as e:
        logger.warning(f"Failed to update progress for item {item_id}: {e}")


def _update_league_stats(user_id, correct_count, total_questions):
    """Update league member stats after a practice session.

    Args:
        user_id: User ID
        correct_count: Number of correct answers in this session
        total_questions: Total questions in this session

    Returns:
        dict with updated stats or None if user not in a league
    """
    try:
        # Get user record to check for leagueId
        users_table = dynamodb.Table(USERS_TABLE)
        user_response = users_table.get_item(Key={'userId': user_id})
        user = user_response.get('Item')

        if not user or not user.get('leagueId'):
            return None

        league_id = user['leagueId']

        # Calculate dates in Europe/Berlin timezone (UTC+2 approximation)
        now_berlin = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        today = now_berlin.strftime('%Y-%m-%d')
        yesterday = (now_berlin - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        monday = (now_berlin - datetime.timedelta(days=now_berlin.weekday())).strftime('%Y-%m-%d')

        # Get current league member record
        members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
        member_response = members_table.get_item(
            Key={'leagueId': league_id, 'userId': user_id}
        )
        member = member_response.get('Item')

        if not member:
            return None

        # Calculate new values
        new_total_correct = int(member.get('totalCorrect', 0)) + correct_count
        new_total_attempts = int(member.get('totalAttempts', 0)) + total_questions

        # Weekly reset logic
        week_start_date = member.get('weekStartDate', '')
        if week_start_date != monday:
            new_weekly_correct = correct_count
            new_week_start_date = monday
        else:
            new_weekly_correct = int(member.get('weeklyCorrect', 0)) + correct_count
            new_week_start_date = monday

        # Streak logic
        last_practice_date = member.get('lastPracticeDate', '')
        current_streak = int(member.get('currentStreak', 0))

        if last_practice_date == today:
            # Already practiced today, no streak change
            new_streak = current_streak
        elif last_practice_date == yesterday:
            # Consecutive day, increment streak
            new_streak = current_streak + 1
        else:
            # Streak broken or first practice
            new_streak = 1

        # Update member record
        members_table.update_item(
            Key={'leagueId': league_id, 'userId': user_id},
            UpdateExpression=(
                'SET totalCorrect = :tc, totalAttempts = :ta, '
                'weeklyCorrect = :wc, weekStartDate = :wsd, '
                'currentStreak = :cs, lastPracticeDate = :lpd'
            ),
            ExpressionAttributeValues={
                ':tc': new_total_correct,
                ':ta': new_total_attempts,
                ':wc': new_weekly_correct,
                ':wsd': new_week_start_date,
                ':cs': new_streak,
                ':lpd': today,
            }
        )

        logger.info(json.dumps({
            'event': 'league_stats_updated',
            'userId': user_id,
            'leagueId': league_id,
            'totalCorrect': new_total_correct,
            'currentStreak': new_streak,
            'weeklyCorrect': new_weekly_correct,
        }))

        return {
            'totalCorrect': new_total_correct,
            'currentStreak': new_streak,
            'weeklyCorrect': new_weekly_correct,
        }

    except Exception as e:
        logger.warning(f"Failed to update league stats for user {user_id}: {e}")
        return None
