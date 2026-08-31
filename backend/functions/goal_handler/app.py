"""Goal Handler - Manage learning goals for VocabTrainer."""

import json
import logging
import math
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

# The deadline is due at 00:00 (local) of the set day. Compute "today" in the
# users' timezone so day boundaries match their expectation (not UTC).
BERLIN_TZ = ZoneInfo('Europe/Berlin')


def _today_local():
    """Return today's date in Europe/Berlin (DST-aware)."""
    return datetime.now(BERLIN_TZ).date()

import boto3
from boto3.dynamodb.conditions import Key

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    generate_uuid,
    get_timestamp,
    parse_body,
    get_path_parameter,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
GOALS_TABLE = os.environ['GOALS_TABLE']
PROGRESS_TABLE = os.environ['PROGRESS_TABLE']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
VOCABITEMS_TABLE = os.environ['VOCABITEMS_TABLE']
USERS_TABLE = os.environ['USERS_TABLE']
LEAGUES_TABLE = os.environ['LEAGUES_TABLE']
LEAGUE_MEMBERS_TABLE = os.environ['LEAGUE_MEMBERS_TABLE']


def lambda_handler(event, context):
    """Route goal requests based on HTTP method and path."""
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(json.dumps({
        'event': 'goal_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        # GET /goals/{goalId}/members — teacher views member progress
        if http_method == 'GET' and '/members' in path:
            return handle_get_member_progress(event, user_id)

        # POST /goals — create a new goal
        if http_method == 'POST' and path.rstrip('/').endswith('/goals'):
            return handle_create(event, user_id)

        # GET /goals — list user's goals
        if http_method == 'GET' and path.rstrip('/').endswith('/goals'):
            return handle_list(event, user_id)

        # GET /goals/{goalId} — get goal detail
        if http_method == 'GET':
            return handle_get(event, user_id)

        # PUT /goals/{goalId} — update goal
        if http_method == 'PUT':
            return handle_update(event, user_id)

        # DELETE /goals/{goalId} — delete goal
        if http_method == 'DELETE':
            return handle_delete(event, user_id)

        return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in goal handler: {e}")
        return build_error_response(e, 'goal_handler')


# ============================================================
# Helper functions
# ============================================================

def _is_teacher(event):
    """Check if the caller is in the 'teachers' Cognito group."""
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    groups = claims.get('cognito:groups', '')
    if isinstance(groups, str):
        return 'teachers' in [g.strip() for g in groups.split(',')]
    return False


def _get_user(user_id):
    """Get user record from Users table."""
    table = dynamodb.Table(USERS_TABLE)
    response = table.get_item(Key={'userId': user_id})
    return response.get('Item')


def _get_league(league_id):
    """Get league record."""
    table = dynamodb.Table(LEAGUES_TABLE)
    response = table.get_item(Key={'leagueId': league_id})
    return response.get('Item')


def _get_goal(goal_id):
    """Get goal by goalId (query by PK only, get first match)."""
    table = dynamodb.Table(GOALS_TABLE)
    response = table.query(
        KeyConditionExpression=Key('goalId').eq(goal_id)
    )
    items = response.get('Items', [])
    return items[0] if items else None


def _parse_date(date_str):
    """Parse an ISO date string (YYYY-MM-DD) into a date object."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError(f"Ungültiges Datum: {date_str}. Format: YYYY-MM-DD")


# ============================================================
# Smart progress calculation
# ============================================================

def calculate_goal_status(goal, user_id):
    """Calculate detailed progress status for a learning goal.

    For each vocabSetId in the goal, queries Progress and VocabItems
    tables to determine mastery status, tempo, and recommendation.

    Args:
        goal: Goal dict from DynamoDB
        user_id: The user to calculate progress for

    Returns:
        dict with progressPercent, masteredWords, totalWords, daysRemaining,
        requiredPerDay, status, recommendation, perSet
    """
    target_mastery = int(goal.get('targetMastery', 4))
    vocab_set_ids = goal.get('vocabSetIds', [])
    deadline_str = goal.get('deadline', '')
    created_at_str = goal.get('createdAt', '')

    # Parse dates. "today" is Berlin-local so the 00:00 deadline boundary
    # matches the user's calendar day (see _today_local).
    today = _today_local()
    try:
        deadline = _parse_date(deadline_str)
    except ValueError:
        deadline = today

    # createdAt might be ISO date string or Unix timestamp
    if isinstance(created_at_str, str) and '-' in created_at_str:
        try:
            created_date = _parse_date(created_at_str)
        except ValueError:
            created_date = today
    else:
        # Unix timestamp
        try:
            created_date = datetime.fromtimestamp(int(created_at_str), BERLIN_TZ).date()
        except (ValueError, TypeError, OSError):
            created_date = today

    days_remaining = (deadline - today).days
    days_elapsed = max((today - created_date).days, 1)

    # Aggregate progress across all vocab sets
    total_words = 0
    mastered_words = 0
    hard_words = 0
    per_set = []

    progress_table = dynamodb.Table(PROGRESS_TABLE)
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)

    # Vocab sets belong to the goal owner (for league-wide goals the teacher).
    goal_owner_id = goal.get('userId', user_id)

    for vocab_set_id in vocab_set_ids:
        # Resolve the set title (fall back to the id if not found)
        set_title = ''
        try:
            vs_resp = vocabsets_table.get_item(
                Key={'vocabSetId': vocab_set_id, 'userId': goal_owner_id}
            )
            set_title = (vs_resp.get('Item') or {}).get('title', '')
        except Exception as e:
            logger.warning(f"Failed to load title for set {vocab_set_id}: {e}")

        # Count total items in this vocab set
        try:
            items_response = items_table.query(
                KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id),
                Select='COUNT'
            )
            set_total = items_response.get('Count', 0)
        except Exception as e:
            logger.warning(f"Failed to count items for set {vocab_set_id}: {e}")
            set_total = 0

        # Query progress for this user + vocab set
        progress_key = f"{user_id}#{vocab_set_id}"
        set_mastered = 0
        set_hard = 0

        try:
            progress_response = progress_table.query(
                KeyConditionExpression=Key('progressKey').eq(progress_key)
            )
            progress_items = progress_response.get('Items', [])

            for p in progress_items:
                mastery = int(p.get('masteryLevel', 0))
                incorrect = int(p.get('incorrectCount', 0))

                if mastery >= target_mastery:
                    set_mastered += 1
                if mastery < 2 and incorrect > 0:
                    set_hard += 1
        except Exception as e:
            logger.warning(f"Failed to query progress for {progress_key}: {e}")
            progress_items = []

        set_percent = round(set_mastered / max(set_total, 1) * 100, 1)
        per_set.append({
            'vocabSetId': vocab_set_id,
            'title': set_title,
            'totalWords': set_total,
            'masteredWords': set_mastered,
            'hardWords': set_hard,
            'progressPercent': set_percent,
        })

        total_words += set_total
        mastered_words += set_mastered
        hard_words += set_hard

    # Calculate overall progress
    progress_percent = round(mastered_words / max(total_words, 1) * 100, 1)

    # Tempo: words mastered per day elapsed
    tempo = mastered_words / max(days_elapsed, 1)

    # Required words per day to meet deadline
    remaining = total_words - mastered_words
    required_per_day = remaining / max(days_remaining, 1) if days_remaining > 0 else remaining

    # Hard words adjustment factor
    hard_factor = 1 + 0.5 * hard_words / max(total_words, 1)
    adjusted_required = required_per_day * hard_factor

    # Determine status
    if progress_percent >= 100:
        status = 'completed'
        recommendation = 'Geschafft! Alle Vokabeln beherrscht.'
    elif days_remaining <= 0:
        status = 'expired'
        recommendation = f'Deadline überschritten. {mastered_words}/{total_words} Wörter beherrscht.'
    elif tempo >= adjusted_required * 0.9:
        status = 'on_track'
        recommendation = 'Du bist im Zeitplan! Übe weiter so.'
    elif tempo >= adjusted_required * 0.5:
        status = 'at_risk'
        n = max(1, math.ceil(adjusted_required))
        recommendation = f'Übe heute {n} Wörter um aufzuholen.'
    else:
        status = 'behind'
        n = max(1, math.ceil(adjusted_required))
        recommendation = f'Du hängst hinterher! Übe heute mindestens {n} Wörter.'

    return {
        'progressPercent': progress_percent,
        'masteredWords': mastered_words,
        'totalWords': total_words,
        'hardWords': hard_words,
        'daysRemaining': days_remaining,
        'daysElapsed': days_elapsed,
        'requiredPerDay': round(required_per_day, 1),
        'tempo': round(tempo, 2),
        'status': status,
        'recommendation': recommendation,
        'perSet': per_set,
    }


# ============================================================
# Route handlers
# ============================================================

def handle_create(event, user_id):
    """Handle POST /goals — Create a new learning goal.

    Expected body:
    {
        "title": "Kapitel 3 bis Freitag",
        "vocabSetIds": ["uuid1", "uuid2"],
        "deadline": "2026-09-05",
        "targetMastery": 4,        (optional, default 4, range 3-5)
        "leagueId": "uuid"         (optional, teacher assigns to league)
    }
    """
    body = parse_body(event)

    title = body.get('title', '').strip()
    if not title:
        return build_response(400, {'error': 'title ist erforderlich'})
    if len(title) > 200:
        return build_response(400, {'error': 'title darf maximal 200 Zeichen lang sein'})

    vocab_set_ids = body.get('vocabSetIds', [])
    if not isinstance(vocab_set_ids, list) or not vocab_set_ids:
        return build_response(400, {'error': 'vocabSetIds muss eine nicht-leere Liste sein'})

    deadline = body.get('deadline', '').strip()
    if not deadline:
        return build_response(400, {'error': 'deadline ist erforderlich (Format: YYYY-MM-DD)'})
    # Validate date format
    _parse_date(deadline)

    target_mastery = int(body.get('targetMastery', 4))
    if target_mastery < 3 or target_mastery > 5:
        return build_response(400, {'error': 'targetMastery muss zwischen 3 und 5 liegen'})

    # League goal: teacher assigns goal to their league
    league_id = body.get('leagueId')
    if league_id:
        if not _is_teacher(event):
            return build_response(403, {'error': 'Nur Lehrkräfte können Liga-Ziele erstellen'})

        league = _get_league(league_id)
        if not league:
            return build_response(404, {'error': 'Liga nicht gefunden'})
        if league.get('teacherUserId') != user_id:
            return build_response(403, {'error': 'Sie können nur Ziele für Ihre eigene Liga erstellen'})

    goal_id = generate_uuid()
    today_str = _today_local().isoformat()

    goal_item = {
        'goalId': goal_id,
        'userId': user_id,
        'title': title,
        'vocabSetIds': vocab_set_ids,
        'deadline': deadline,
        'targetMastery': target_mastery,
        'createdBy': user_id,
        'createdAt': today_str,
        'status': 'active',
    }

    if league_id:
        goal_item['leagueId'] = league_id

    goals_table = dynamodb.Table(GOALS_TABLE)
    goals_table.put_item(Item=goal_item)

    logger.info(json.dumps({
        'event': 'goal_created',
        'goalId': goal_id,
        'userId': user_id,
        'leagueId': league_id or '',
        'vocabSetCount': len(vocab_set_ids),
    }))

    # Include status in response
    goal_status = calculate_goal_status(goal_item, user_id)
    goal_item['progress'] = goal_status

    return build_response(201, goal_item)


def handle_list(event, user_id):
    """Handle GET /goals — List user's goals + league goals.

    Returns all goals the user owns, plus any goals assigned to the
    user's league (by a teacher).
    """
    goals_table = dynamodb.Table(GOALS_TABLE)

    # 1. Get user's own goals via GSI
    response = goals_table.query(
        IndexName='userId-index',
        KeyConditionExpression=Key('userId').eq(user_id)
    )
    own_goals = response.get('Items', [])
    seen_goal_ids = {g['goalId'] for g in own_goals}

    # 2. Get league goals (if user is in a league)
    league_goals = []
    user = _get_user(user_id)
    user_league_id = user.get('leagueId') if user else None

    if user_league_id:
        # Scan goals table for goals with this leagueId
        # (acceptable cost: goals table is small)
        scan_response = goals_table.scan(
            FilterExpression='leagueId = :lid AND #s = :active',
            ExpressionAttributeValues={
                ':lid': user_league_id,
                ':active': 'active',
            },
            ExpressionAttributeNames={
                '#s': 'status',
            }
        )
        for goal in scan_response.get('Items', []):
            if goal['goalId'] not in seen_goal_ids:
                league_goals.append(goal)
                seen_goal_ids.add(goal['goalId'])

    all_goals = own_goals + league_goals

    # Calculate status for each goal
    for goal in all_goals:
        # For league goals, calculate progress for the requesting user
        goal['progress'] = calculate_goal_status(goal, user_id)

    # Sort by deadline ascending (nearest deadline first)
    all_goals.sort(key=lambda g: g.get('deadline', '9999-12-31'))

    logger.info(json.dumps({
        'event': 'goals_listed',
        'userId': user_id,
        'ownCount': len(own_goals),
        'leagueCount': len(league_goals),
    }))

    return build_response(200, {
        'goals': all_goals,
        'total': len(all_goals),
    })


def handle_get(event, user_id):
    """Handle GET /goals/{goalId} — Get goal detail with progress."""
    goal_id = get_path_parameter(event, 'goalId')

    goal = _get_goal(goal_id)
    if not goal:
        return build_response(404, {'error': 'Lernziel nicht gefunden'})

    # Verify access: owner, or league member
    if goal['userId'] != user_id:
        # Check if it's a league goal the user can see
        league_id = goal.get('leagueId')
        if not league_id:
            return build_response(403, {'error': 'Kein Zugriff auf dieses Lernziel'})

        user = _get_user(user_id)
        user_league_id = user.get('leagueId') if user else None

        # Allow if user's league matches, or user is the league teacher
        if user_league_id != league_id:
            league = _get_league(league_id)
            if not league or league.get('teacherUserId') != user_id:
                return build_response(403, {'error': 'Kein Zugriff auf dieses Lernziel'})

    # Calculate full progress status for the requesting user
    goal['progress'] = calculate_goal_status(goal, user_id)

    return build_response(200, goal)


def handle_update(event, user_id):
    """Handle PUT /goals/{goalId} — Update goal. Only owner can update.

    Expected body (all optional):
    {
        "title": "Updated title",
        "vocabSetIds": ["uuid1", "uuid2"],
        "deadline": "2026-09-10",
        "targetMastery": 5
    }
    """
    goal_id = get_path_parameter(event, 'goalId')

    goal = _get_goal(goal_id)
    if not goal:
        return build_response(404, {'error': 'Lernziel nicht gefunden'})

    if goal['userId'] != user_id:
        return build_response(403, {'error': 'Nur der Ersteller kann dieses Lernziel bearbeiten'})

    body = parse_body(event)

    update_parts = []
    expr_values = {}
    expr_names = {}

    if 'title' in body:
        title = body['title'].strip()
        if not title:
            return build_response(400, {'error': 'title darf nicht leer sein'})
        if len(title) > 200:
            return build_response(400, {'error': 'title darf maximal 200 Zeichen lang sein'})
        update_parts.append('title = :title')
        expr_values[':title'] = title

    if 'vocabSetIds' in body:
        vocab_set_ids = body['vocabSetIds']
        if not isinstance(vocab_set_ids, list) or not vocab_set_ids:
            return build_response(400, {'error': 'vocabSetIds muss eine nicht-leere Liste sein'})
        update_parts.append('vocabSetIds = :vsids')
        expr_values[':vsids'] = vocab_set_ids

    if 'deadline' in body:
        deadline = body['deadline'].strip()
        _parse_date(deadline)  # validate
        update_parts.append('deadline = :deadline')
        expr_values[':deadline'] = deadline

    if 'targetMastery' in body:
        target_mastery = int(body['targetMastery'])
        if target_mastery < 3 or target_mastery > 5:
            return build_response(400, {'error': 'targetMastery muss zwischen 3 und 5 liegen'})
        update_parts.append('targetMastery = :tm')
        expr_values[':tm'] = target_mastery

    if not update_parts:
        return build_response(400, {'error': 'Keine Felder zum Aktualisieren angegeben'})

    goals_table = dynamodb.Table(GOALS_TABLE)
    kwargs = {
        'Key': {'goalId': goal_id, 'userId': user_id},
        'UpdateExpression': 'SET ' + ', '.join(update_parts),
        'ExpressionAttributeValues': expr_values,
        'ReturnValues': 'ALL_NEW',
    }
    if expr_names:
        kwargs['ExpressionAttributeNames'] = expr_names

    response = goals_table.update_item(**kwargs)
    updated_goal = response.get('Attributes', {})

    # Include progress status
    updated_goal['progress'] = calculate_goal_status(updated_goal, user_id)

    logger.info(json.dumps({
        'event': 'goal_updated',
        'goalId': goal_id,
        'userId': user_id,
    }))

    return build_response(200, updated_goal)


def handle_delete(event, user_id):
    """Handle DELETE /goals/{goalId} — Delete goal. Only owner can delete."""
    goal_id = get_path_parameter(event, 'goalId')

    goal = _get_goal(goal_id)
    if not goal:
        return build_response(404, {'error': 'Lernziel nicht gefunden'})

    if goal['userId'] != user_id:
        return build_response(403, {'error': 'Nur der Ersteller kann dieses Lernziel löschen'})

    goals_table = dynamodb.Table(GOALS_TABLE)
    goals_table.delete_item(Key={
        'goalId': goal_id,
        'userId': user_id,
    })

    logger.info(json.dumps({
        'event': 'goal_deleted',
        'goalId': goal_id,
        'userId': user_id,
    }))

    return build_response(200, {'message': 'Lernziel gelöscht'})


# ============================================================
# Teacher integration: member progress
# ============================================================

def handle_get_member_progress(event, user_id):
    """Handle GET /goals/{goalId}/members — Teacher views all member progress.

    Only accessible by the teacher who created the goal (and the goal
    must have a leagueId).

    Returns per-member progress: userId, displayName, progressPercent,
    status, masteredWords, totalWords.
    """
    goal_id = get_path_parameter(event, 'goalId')

    goal = _get_goal(goal_id)
    if not goal:
        return build_response(404, {'error': 'Lernziel nicht gefunden'})

    # Must be creator (teacher)
    if goal.get('createdBy', goal.get('userId')) != user_id:
        return build_response(403, {'error': 'Nur der Ersteller kann den Fortschritt der Mitglieder einsehen'})

    league_id = goal.get('leagueId')
    if not league_id:
        return build_response(400, {'error': 'Dieses Lernziel ist keiner Liga zugeordnet'})

    # Verify this is the league's teacher
    league = _get_league(league_id)
    if not league or league.get('teacherUserId') != user_id:
        return build_response(403, {'error': 'Kein Zugriff — Sie sind nicht der Lehrer dieser Liga'})

    # Get all league members
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    members_response = members_table.query(
        KeyConditionExpression=Key('leagueId').eq(league_id)
    )
    members = members_response.get('Items', [])

    # Calculate progress for each member
    member_progress = []
    for member in members:
        member_user_id = member['userId']
        display_name = member.get('displayName', 'Unbekannt')

        status_data = calculate_goal_status(goal, member_user_id)

        member_progress.append({
            'userId': member_user_id,
            'displayName': display_name,
            'progressPercent': status_data['progressPercent'],
            'status': status_data['status'],
            'masteredWords': status_data['masteredWords'],
            'totalWords': status_data['totalWords'],
            'daysRemaining': status_data['daysRemaining'],
            'recommendation': status_data['recommendation'],
        })

    # Sort by progress descending
    member_progress.sort(key=lambda m: m['progressPercent'], reverse=True)

    logger.info(json.dumps({
        'event': 'member_progress_viewed',
        'goalId': goal_id,
        'leagueId': league_id,
        'memberCount': len(member_progress),
        'viewedBy': user_id,
    }))

    return build_response(200, {
        'goalId': goal_id,
        'leagueId': league_id,
        'members': member_progress,
    })
