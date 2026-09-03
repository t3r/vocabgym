"""Progress Handler - Retrieve progress statistics and analytics."""

import json
import logging
import os
import datetime
import math
from collections import defaultdict

import boto3
from boto3.dynamodb.conditions import Key

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    get_path_parameter,
    get_timestamp,
)
from lib.validation import validate_uuid

from lib.error_clusters import build_error_clusters
from learning_tips import generate_tips
from learning_tips_cache import get_or_generate

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
PROGRESS_TABLE = os.environ['PROGRESS_TABLE']
SESSIONS_TABLE = os.environ['SESSIONS_TABLE']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
USERS_TABLE = os.environ.get('USERS_TABLE', '')
LEAGUES_TABLE = os.environ.get('LEAGUES_TABLE', '')


def lambda_handler(event, context):
    """Route progress requests.

    Routes:
    - GET /progress/overview: Overall user progress
    - GET /progress/{vocabSetId}: Progress for specific vocab set
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    path_params = event.get('pathParameters') or {}

    logger.info(json.dumps({
        'event': 'progress_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        if '/overview' in path:
            return handle_overview(event, user_id)
        elif path_params.get('vocabSetId'):
            return handle_vocab_set_progress(event, user_id)
        else:
            return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in progress handler: {e}")
        return build_error_response(e, 'progress_handler')


def handle_overview(event, user_id):
    """Handle GET /progress/overview - Get overall user progress.

    Returns aggregate statistics across all vocabulary sets.
    """
    # Collect ALL sets the user practices: their own sets PLUS any sets assigned
    # to their league. A league-only student owns no sets, so aggregating over
    # owned sets alone would show an empty mastery distribution / weakest-words
    # list even though they have plenty of progress. We therefore build the
    # union {vocabSetId -> {title, itemCount}} from both sources.
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    owned_resp = vocabsets_table.query(
        IndexName='userId-createdAt-index',
        KeyConditionExpression=Key('userId').eq(user_id),
    )
    owned_sets = owned_resp.get('Items', [])

    set_meta = {}  # vocabSetId -> {'title':..., 'itemCount':..., 'targetLanguage':...}
    for vs in owned_sets:
        set_meta[vs['vocabSetId']] = {
            'title': vs.get('title', ''),
            'itemCount': int(vs.get('itemCount', 0) or 0),
            'targetLanguage': vs.get('targetLanguage', 'fr') or 'fr',
        }

    # Add league-assigned sets (fetched by their teacher owner — deterministic,
    # same resolution as handle_vocab_set_progress).
    try:
        users_table = dynamodb.Table(USERS_TABLE)
        user = users_table.get_item(Key={'userId': user_id}).get('Item', {})
        league_id = user.get('leagueId')
        if league_id and LEAGUES_TABLE:
            leagues_table = dynamodb.Table(LEAGUES_TABLE)
            league = leagues_table.get_item(Key={'leagueId': league_id}).get('Item', {})
            teacher_user_id = league.get('teacherUserId')
            for assigned_id in league.get('vocabSetIds', []) or []:
                if assigned_id in set_meta or not teacher_user_id:
                    continue
                ts = vocabsets_table.get_item(
                    Key={'vocabSetId': assigned_id, 'userId': teacher_user_id}
                ).get('Item')
                if ts:
                    set_meta[assigned_id] = {
                        'title': ts.get('title', ''),
                        'itemCount': int(ts.get('itemCount', 0) or 0),
                        'targetLanguage': ts.get('targetLanguage', 'fr') or 'fr',
                    }
    except Exception as e:
        logger.warning(f"Failed to resolve league sets for overview: {e}")

    # Get the user's practice sessions. Note: this table's sort key is sessionId
    # (a random UUID), so neither the query order nor a Limit here reflects
    # recency. Fetch the user's sessions (90-day TTL keeps this bounded) and
    # order by completedAt below so "recent" is truly the most recent.
    sessions_table = dynamodb.Table(SESSIONS_TABLE)
    sessions = []
    query_kwargs = {'KeyConditionExpression': Key('userId').eq(user_id)}
    while True:
        sessions_response = sessions_table.query(**query_kwargs)
        sessions.extend(sessions_response.get('Items', []))
        last_key = sessions_response.get('LastEvaluatedKey')
        if not last_key:
            break
        query_kwargs['ExclusiveStartKey'] = last_key

    # Filter completed sessions, most-recent first. The sessions query sorts by
    # the table's sort key (sessionId, a random UUID) — NOT by time — so we must
    # explicitly order by completedAt descending here before taking the latest.
    completed_sessions = [s for s in sessions if s.get('status') == 'completed']
    completed_sessions.sort(key=lambda s: int(s.get('completedAt', 0)), reverse=True)

    # Aggregate progress across ALL practised sets (owned + league).
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    total_words = 0
    practiced_words = 0
    mastery_sum = 0
    mastery_distribution = defaultdict(int)
    total_correct = 0
    total_incorrect = 0

    # Collect weakest words (practiced but low mastery or high error count)
    weak_items = []

    for vocab_set_id, meta in set_meta.items():
        vocab_set_title = meta['title']
        total_words += meta['itemCount']

        # Get progress for this vocab set
        progress_key = f"{user_id}#{vocab_set_id}"
        prog_response = progress_table.query(
            KeyConditionExpression=Key('progressKey').eq(progress_key)
        )
        progress_items = prog_response.get('Items', [])

        for item in progress_items:
            practiced_words += 1
            mastery = int(item.get('masteryLevel', 0))
            mastery_sum += mastery
            mastery_distribution[mastery] += 1
            correct = int(item.get('correctCount', 0))
            incorrect = int(item.get('incorrectCount', 0))
            total_correct += correct
            total_incorrect += incorrect

            # Track weak items (any word with at least 1 error, or low mastery)
            if incorrect > 0 or (mastery < 3 and (correct + incorrect) > 0):
                weak_items.append({
                    'vocabSetId': vocab_set_id,
                    'vocabSetTitle': vocab_set_title,
                    'itemId': item.get('itemId', ''),
                    'masteryLevel': mastery,
                    'correctCount': correct,
                    'incorrectCount': incorrect,
                    'recentErrors': item.get('recentErrors', []),
                })

    # Build a daily-aggregated activity series over the last 30 days from ALL
    # completed sessions (not just the last 10), so the activity chart shows a
    # real history. A heavy day of many sessions is one point; days with no
    # practice are simply absent. Ordered oldest→newest for charting.
    DAYS_WINDOW = 30
    cutoff = get_timestamp() - DAYS_WINDOW * 24 * 60 * 60
    by_day = {}
    for s in completed_sessions:
        ts = int(s.get('completedAt', 0) or 0)
        if ts < cutoff:
            continue
        day = datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
        d = by_day.setdefault(day, {'correct': 0, 'total': 0, 'sessions': 0})
        d['correct'] += int(s.get('correctAnswers', 0) or 0)
        d['total'] += int(s.get('totalQuestions', 0) or 0)
        d['sessions'] += 1
    activity_by_day = [
        {
            'date': day,
            'correct': v['correct'],
            'total': v['total'],
            'sessions': v['sessions'],
            'accuracy': round(v['correct'] / v['total'] * 100) if v['total'] > 0 else 0,
        }
        for day, v in sorted(by_day.items())
    ]

    # Calculate averages
    avg_mastery = round(mastery_sum / practiced_words, 1) if practiced_words > 0 else 0
    total_attempts = total_correct + total_incorrect
    overall_accuracy = round(
        (total_correct / total_attempts * 100) if total_attempts > 0 else 0, 1
    )

    # Forecast: when will the learner reach "sicher" (level>=4) and "beherrscht"
    # (all words level>=4), if they keep up the current pace.
    forecast = _mastery_forecast(
        mastery_distribution=mastery_distribution,
        total_words=total_words,
        practiced_words=practiced_words,
        active_days=len(by_day),
    )

    # Calculate total time spent
    total_time_seconds = sum(s.get('duration', 0) for s in completed_sessions)

    # Practice streak
    practice_streak = _calculate_streak(completed_sessions)

    # Get top 10 weakest words with their vocab text
    weak_items.sort(key=lambda x: (x['masteryLevel'], -x['incorrectCount']))
    top_weak = weak_items[:10]

    # Batch lookup vocab item texts
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    weakest_words = []
    for w in top_weak:
        try:
            item_resp = items_table.get_item(
                Key={'vocabSetId': w['vocabSetId'], 'itemId': w['itemId']}
            )
            vi = item_resp.get('Item', {})
            total_attempts = w['correctCount'] + w['incorrectCount']
            accuracy = round(w['correctCount'] / total_attempts * 100) if total_attempts > 0 else 0
            weakest_words.append({
                'source': vi.get('source', vi.get('german', '')),
                'target': vi.get('target', vi.get('french', '')),
                'vocabSetTitle': w['vocabSetTitle'],
                'masteryLevel': w['masteryLevel'],
                'accuracy': accuracy,
                'incorrectCount': w['incorrectCount'],
                'recentErrors': [e.get('answer', '') for e in w['recentErrors'][-3:]],
            })
        except Exception:
            pass

    # Learning tips: cluster the weak words' mistakes by type and let the LLM
    # phrase short German tips (cached per user; only regenerated when the error
    # fingerprint changes). Uses the top weak words we already resolved (with
    # source/target text + recent wrong answers) so no extra item reads.
    learning_tips = []
    try:
        if weakest_words:
            # Pick the dominant target language among the practised sets.
            langs = [m.get('targetLanguage', 'fr') for m in set_meta.values()]
            target_language = max(set(langs), key=langs.count) if langs else 'fr'
            clusters = build_error_clusters(weakest_words, target_language)
            if clusters:
                learning_tips = get_or_generate(user_id, clusters, generate_tips)
    except Exception as e:
        logger.warning(json.dumps({'event': 'learning_tips_failed', 'error': str(e)}))
        learning_tips = []

    # Format recent sessions for response
    recent_sessions = [
        {
            'sessionId': s['sessionId'],
            'vocabSetId': s.get('vocabSetId', ''),
            'score': s.get('score', 0),
            'correct': s.get('correctAnswers', 0),
            'total': s.get('totalQuestions', 0),
            'duration': s.get('duration', 0),
            'completedAt': s.get('completedAt', 0),
            'direction': s.get('direction', 'de-fr'),
            'mode': s.get('mode', 'practice'),
        }
        for s in completed_sessions[:10]
    ]

    logger.info(json.dumps({
        'event': 'progress_overview',
        'userId': user_id,
        'totalVocabSets': len(set_meta),
        'totalWords': int(total_words),
        'practicedWords': int(practiced_words),
    }, default=str))

    return build_response(200, {
        'totalVocabSets': len(set_meta),
        'totalWords': total_words,
        'practicedWords': practiced_words,
        'averageMastery': avg_mastery,
        'overallAccuracy': overall_accuracy,
        'totalSessions': len(completed_sessions),
        'totalTimeSeconds': total_time_seconds,
        'practiceStreak': practice_streak,
        'masteryDistribution': {
            '0': mastery_distribution.get(0, 0),
            '1': mastery_distribution.get(1, 0),
            '2': mastery_distribution.get(2, 0),
            '3': mastery_distribution.get(3, 0),
            '4': mastery_distribution.get(4, 0),
            '5': mastery_distribution.get(5, 0),
        },
        'recentSessions': recent_sessions,
        'activityByDay': activity_by_day,
        'forecast': forecast,
        'learningTips': learning_tips,
        'weakestWords': weakest_words,
    })


def handle_vocab_set_progress(event, user_id):
    """Handle GET /progress/{vocabSetId} - Get progress for a specific vocab set."""
    vocab_set_id = get_path_parameter(event, 'vocabSetId')

    is_valid, err = validate_uuid(vocab_set_id, 'vocabSetId')
    if not is_valid:
        return build_response(400, {'error': err})

    # SECURITY: Verify ownership or league assignment before accessing vocab items.
    # This prevents IDOR attacks where any user could view another user's
    # vocabulary items and progress data by guessing/enumerating vocabSetIds.
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    vocab_set_resp = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )
    vocab_set = vocab_set_resp.get('Item')

    if not vocab_set:
        # Not owned by caller. Check if it's a league-assigned set.
        users_table = dynamodb.Table(USERS_TABLE)
        user = users_table.get_item(Key={'userId': user_id}).get('Item', {})
        league_id = user.get('leagueId')

        if not league_id:
            return build_response(404, {'error': 'Vocabulary set not found'})

        leagues_table = dynamodb.Table(LEAGUES_TABLE)
        league = leagues_table.get_item(Key={'leagueId': league_id}).get('Item', {})
        assigned_ids = league.get('vocabSetIds', [])
        teacher_user_id = league.get('teacherUserId')

        if vocab_set_id not in assigned_ids or not teacher_user_id:
            return build_response(404, {'error': 'Vocabulary set not found'})

        vocab_set_resp = vocabsets_table.get_item(
            Key={'vocabSetId': vocab_set_id, 'userId': teacher_user_id}
        )
        vocab_set = vocab_set_resp.get('Item')
        if not vocab_set:
            return build_response(404, {'error': 'Vocabulary set not found'})

    # Get vocab items (only active ones, now authorized)
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    items_response = items_table.query(
        KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
    )
    items = [item for item in items_response.get('Items', []) if item.get('isActive', True)]

    # Get progress for all items in this set
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    progress_key = f"{user_id}#{vocab_set_id}"
    prog_response = progress_table.query(
        KeyConditionExpression=Key('progressKey').eq(progress_key)
    )
    progress_items = prog_response.get('Items', [])

    # Map progress by itemId
    progress_map = {p['itemId']: p for p in progress_items}

    # Build detailed progress per item
    item_progress = []
    mastered_count = 0
    in_progress_count = 0
    not_practiced_count = 0
    total_correct = 0
    total_incorrect = 0

    for item in items:
        item_id = item['itemId']
        progress = progress_map.get(item_id, {})

        correct = progress.get('correctCount', 0)
        incorrect = progress.get('incorrectCount', 0)
        mastery = progress.get('masteryLevel', 0)
        total_attempts = correct + incorrect

        total_correct += correct
        total_incorrect += incorrect

        if total_attempts == 0:
            not_practiced_count += 1
        elif mastery >= 4:
            mastered_count += 1
        else:
            in_progress_count += 1

        accuracy = round((correct / total_attempts * 100) if total_attempts > 0 else 0, 1)

        item_progress.append({
            'itemId': item_id,
            'source': item.get('source', item.get('german', '')),
            'target': item.get('target', item.get('french', '')),
            'correctCount': correct,
            'incorrectCount': incorrect,
            'accuracy': accuracy,
            'masteryLevel': mastery,
            'lastPracticedAt': progress.get('lastPracticedAt', 0),
            'consecutiveCorrect': progress.get('consecutiveCorrect', 0),
            'recentErrors': progress.get('recentErrors', []),
        })

    # Sort by mastery level (lowest first - words needing most practice)
    item_progress.sort(key=lambda x: (x['masteryLevel'], x['accuracy']))

    total_attempts = total_correct + total_incorrect
    overall_accuracy = round(
        (total_correct / total_attempts * 100) if total_attempts > 0 else 0, 1
    )

    return build_response(200, {
        'vocabSetId': vocab_set_id,
        'totalItems': len(items),
        'masteredCount': mastered_count,
        'inProgressCount': in_progress_count,
        'notPracticedCount': not_practiced_count,
        'overallAccuracy': overall_accuracy,
        'progress': item_progress,
    })


def _mastery_forecast(mastery_distribution, total_words, practiced_words, active_days):
    """Estimate when the learner reaches "sicher" (all words >= level 4) and,
    as an interim milestone, how far they already are.

    Heuristic, deliberately conservative and honest about its limits:
    - "secured" words = those at level >= 4 (matches the goal/mastery threshold).
    - remaining words = every active word not yet at level >= 4, INCLUDING words
      never practised yet (total_words - practiced_words).
    - pace = secured words per active practice day so far.
    - The still-weak words are the *hard* ones (the easy words are already
      secured), so they rise slower than the past average. We apply a slowdown
      factor to the projection instead of pretending the past rate continues
      linearly.

    Returns a dict (or a 'not enough data' variant) — never raises.
    """
    SECURE_LEVEL = 4
    # Words already secured vs. still to go.
    secured = sum(mastery_distribution.get(lvl, 0) for lvl in (4, 5))
    # Everything active that is not yet secured — practised-but-weak PLUS
    # not-yet-practised words in the sets.
    weak_practiced = practiced_words - secured
    untrained = max(0, total_words - practiced_words)
    remaining = max(0, weak_practiced + untrained)

    result = {
        'secureLevel': SECURE_LEVEL,
        'totalWords': int(total_words),
        'securedWords': int(secured),
        'remainingWords': int(remaining),
        'alreadySecured': remaining == 0 and total_words > 0,
    }

    # Already there.
    if total_words > 0 and remaining == 0:
        result['note'] = 'Stark! Alle Wörter sind bereits auf „sicher" oder höher. 🎉'
        result['estimatedDays'] = 0
        return result

    # Not enough signal to project a rate yet.
    if secured <= 0 or active_days <= 0:
        result['estimatedDays'] = None
        result['note'] = (
            'Übe noch ein paar Tage weiter — dann kann ich eine Prognose wagen, '
            'wann du „sicher" erreichst.'
        )
        return result

    # Past pace: secured words per active practice day.
    per_day = secured / active_days
    # The remaining words are the stubborn ones; assume they take ~40% longer
    # than the past average pace (slowdown factor 1.4).
    SLOWDOWN = 1.4
    est_days = int(math.ceil((remaining / per_day) * SLOWDOWN)) if per_day > 0 else None

    result['estimatedDays'] = est_days
    if est_days is not None:
        target = datetime.date.today() + datetime.timedelta(days=est_days)
        result['estimatedDate'] = target.isoformat()
        weeks = est_days / 7.0
        when = (
            f'in etwa {est_days} Übungstagen'
            if est_days < 14 else
            f'in etwa {round(weeks)} Wochen (Übungstage)'
        )
        result['note'] = (
            f'Bei gleichem Tempo erreichst du „sicher" für alle Wörter '
            f'voraussichtlich {when}. Die verbleibenden {remaining} Wörter sind '
            f'die hartnäckigen — sie steigen langsamer als der bisherige '
            f'Durchschnitt, deshalb ist die Schätzung bewusst vorsichtig.'
        )
    return result


def _calculate_streak(completed_sessions):
    """Calculate practice streak (consecutive days with at least one session).

    Args:
        completed_sessions: List of completed session records sorted by date desc

    Returns:
        int: Number of consecutive days with practice
    """
    if not completed_sessions:
        return 0

    import datetime

    # Get unique practice dates
    practice_dates = set()
    for session in completed_sessions:
        completed_at = session.get('completedAt', 0)
        if completed_at:
            dt = datetime.datetime.fromtimestamp(int(completed_at), tz=datetime.timezone.utc)
            practice_dates.add(dt.date())

    if not practice_dates:
        return 0

    # Sort dates descending
    sorted_dates = sorted(practice_dates, reverse=True)

    # Check if today or yesterday is in the list (streak must be current)
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    yesterday = today - datetime.timedelta(days=1)

    if sorted_dates[0] != today and sorted_dates[0] != yesterday:
        return 0

    # Count consecutive days
    streak = 1
    for i in range(1, len(sorted_dates)):
        expected_date = sorted_dates[i - 1] - datetime.timedelta(days=1)
        if sorted_dates[i] == expected_date:
            streak += 1
        else:
            break

    return streak
