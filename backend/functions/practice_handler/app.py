"""Practice Handler - Manage practice sessions with answer validation."""

import json
import logging
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
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
SESSIONS_TABLE = os.environ['SESSIONS_TABLE']
PROGRESS_TABLE = os.environ['PROGRESS_TABLE']

# TTL: 90 days for practice sessions
SESSION_TTL_DAYS = 90


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

    # Fetch vocabulary items
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

    # Shuffle and limit
    random.shuffle(active_items)
    if question_count and question_count < len(active_items):
        active_items = active_items[:question_count]

    # Create session
    session_id = generate_uuid()
    timestamp = get_timestamp()
    expires_at = timestamp + (SESSION_TTL_DAYS * 24 * 60 * 60)

    # Build questions
    questions = []
    for i, item in enumerate(active_items):
        question_id = generate_uuid()
        if direction == 'de-fr':
            question_text = item['german']
            correct_answer = item['french']
        else:
            question_text = item['french']
            correct_answer = item['german']

        questions.append({
            'questionId': question_id,
            'itemId': item['itemId'],
            'german': item['german'],
            'french': item['french'],
            'question': question_text,
            'correctAnswer': correct_answer,
            'questionNumber': i + 1,
        })

    # Store session in DynamoDB
    sessions_table = dynamodb.Table(SESSIONS_TABLE)
    sessions_table.put_item(
        Item={
            'userId': user_id,
            'sessionId': session_id,
            'vocabSetId': vocab_set_id,
            'direction': direction,
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
        'totalQuestions': len(questions),
        'questions': [
            {
                'questionId': q['questionId'],
                'itemId': q['itemId'],
                'question': q['question'],
                'correctAnswer': q['correctAnswer'],
                'questionNumber': q['questionNumber'],
                'totalQuestions': len(questions),
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
    _update_item_progress(user_id, session['vocabSetId'], question['itemId'], is_correct)

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

    # Calculate statistics
    timestamp = get_timestamp()
    started_at = session.get('startedAt', timestamp)
    duration = timestamp - started_at
    correct_count = sum(1 for r in client_results if r.get('correct'))
    total = len(client_results) if client_results else session['totalQuestions']
    score = int((correct_count / total * 100) if total > 0 else 0)

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
            _update_item_progress(user_id, vocab_set_id, item_id, result.get('correct', False))

    logger.info(json.dumps({
        'event': 'practice_completed',
        'sessionId': session_id,
        'userId': user_id,
        'score': score,
        'correct': correct_count,
        'total': total,
        'duration': duration,
    }))

    return build_response(200, {
        'sessionId': session_id,
        'score': score,
        'correct': correct_count,
        'total': total,
        'duration': duration,
        'detailedResults': client_results,
    })


def _update_item_progress(user_id, vocab_set_id, item_id, is_correct):
    """Update the progress table for a specific vocabulary item.

    Args:
        user_id: User ID
        vocab_set_id: Vocabulary set ID
        item_id: Vocabulary item ID
        is_correct: Whether the answer was correct
    """
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    progress_key = f"{user_id}#{vocab_set_id}"
    timestamp = get_timestamp()

    try:
        # Try to update existing record
        if is_correct:
            update_expr = (
                'SET correctCount = if_not_exists(correctCount, :zero) + :one, '
                'lastPracticedAt = :ts, '
                'consecutiveCorrect = if_not_exists(consecutiveCorrect, :zero) + :one'
            )
        else:
            update_expr = (
                'SET incorrectCount = if_not_exists(incorrectCount, :zero) + :one, '
                'lastPracticedAt = :ts, '
                'consecutiveCorrect = :zero'
            )

        progress_table.update_item(
            Key={'progressKey': progress_key, 'itemId': item_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues={
                ':one': 1,
                ':zero': 0,
                ':ts': timestamp,
            }
        )

        # Recalculate mastery level
        response = progress_table.get_item(
            Key={'progressKey': progress_key, 'itemId': item_id}
        )
        item = response.get('Item', {})
        correct = item.get('correctCount', 0)
        incorrect = item.get('incorrectCount', 0)
        total_attempts = correct + incorrect

        if total_attempts == 0:
            mastery = 0
        else:
            mastery = min(5, int((correct / total_attempts) * 5))

        progress_table.update_item(
            Key={'progressKey': progress_key, 'itemId': item_id},
            UpdateExpression='SET masteryLevel = :mastery, userId = :uid, vocabSetId = :vsid',
            ExpressionAttributeValues={
                ':mastery': mastery,
                ':uid': user_id,
                ':vsid': vocab_set_id,
            }
        )

    except Exception as e:
        logger.warning(f"Failed to update progress for item {item_id}: {e}")
