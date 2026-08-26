"""Progress Handler - Retrieve progress statistics and analytics."""

import json
import logging
import os
from collections import defaultdict

import boto3
from boto3.dynamodb.conditions import Key

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    get_path_parameter,
)
from lib.validation import validate_uuid

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
PROGRESS_TABLE = os.environ['PROGRESS_TABLE']
SESSIONS_TABLE = os.environ['SESSIONS_TABLE']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']


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
    # Get all vocab sets for user
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    vs_response = vocabsets_table.query(
        IndexName='userId-createdAt-index',
        KeyConditionExpression=Key('userId').eq(user_id),
    )
    vocab_sets = vs_response.get('Items', [])

    # Get recent practice sessions
    sessions_table = dynamodb.Table(SESSIONS_TABLE)
    sessions_response = sessions_table.query(
        KeyConditionExpression=Key('userId').eq(user_id),
        ScanIndexForward=False,
        Limit=20,
    )
    sessions = sessions_response.get('Items', [])

    # Filter completed sessions
    completed_sessions = [s for s in sessions if s.get('status') == 'completed']

    # Aggregate progress data across all vocab sets
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    total_words = 0
    practiced_words = 0
    mastery_sum = 0
    mastery_distribution = defaultdict(int)
    total_correct = 0
    total_incorrect = 0

    for vs in vocab_sets:
        vocab_set_id = vs['vocabSetId']
        total_words += vs.get('itemCount', 0)

        # Get progress for this vocab set
        progress_key = f"{user_id}#{vocab_set_id}"
        prog_response = progress_table.query(
            KeyConditionExpression=Key('progressKey').eq(progress_key)
        )
        progress_items = prog_response.get('Items', [])

        for item in progress_items:
            practiced_words += 1
            mastery = item.get('masteryLevel', 0)
            mastery_sum += mastery
            mastery_distribution[mastery] += 1
            total_correct += item.get('correctCount', 0)
            total_incorrect += item.get('incorrectCount', 0)

    # Calculate averages
    avg_mastery = round(mastery_sum / practiced_words, 1) if practiced_words > 0 else 0
    total_attempts = total_correct + total_incorrect
    overall_accuracy = round(
        (total_correct / total_attempts * 100) if total_attempts > 0 else 0, 1
    )

    # Calculate total time spent
    total_time_seconds = sum(s.get('duration', 0) for s in completed_sessions)

    # Calculate practice streak (consecutive days)
    practice_streak = _calculate_streak(completed_sessions)

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
        }
        for s in completed_sessions[:10]
    ]

    logger.info(json.dumps({
        'event': 'progress_overview',
        'userId': user_id,
        'totalVocabSets': len(vocab_sets),
        'totalWords': int(total_words),
        'practicedWords': int(practiced_words),
    }, default=str))

    return build_response(200, {
        'totalVocabSets': len(vocab_sets),
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
    })


def handle_vocab_set_progress(event, user_id):
    """Handle GET /progress/{vocabSetId} - Get progress for a specific vocab set."""
    vocab_set_id = get_path_parameter(event, 'vocabSetId')

    is_valid, err = validate_uuid(vocab_set_id, 'vocabSetId')
    if not is_valid:
        return build_response(400, {'error': err})

    # Get vocab items (only active ones)
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
