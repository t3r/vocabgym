"""League Handler - Manage leagues (Liga) for VocabTrainer."""

import json
import logging
import os
import random
import string
import datetime

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
cognito_client = boto3.client('cognito-idp')

# Environment variables
LEAGUES_TABLE = os.environ['LEAGUES_TABLE']
LEAGUE_MEMBERS_TABLE = os.environ['LEAGUE_MEMBERS_TABLE']
USERS_TABLE = os.environ['USERS_TABLE']
VOCABSETS_TABLE = os.environ['VOCABSETS_TABLE']
PROGRESS_TABLE = os.environ['PROGRESS_TABLE']
SESSIONS_TABLE = os.environ['SESSIONS_TABLE']
USER_POOL_ID = os.environ.get('USER_POOL_ID', '')


def lambda_handler(event, context):
    """Route league requests based on HTTP method and path."""
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(json.dumps({
        'event': 'league_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        user_id = get_user_id_from_event(event)

        # PUT /users/profile
        if http_method == 'PUT' and '/users/profile' in path:
            return handle_update_profile(event, user_id)

        # GET /users/profile
        if http_method == 'GET' and '/users/profile' in path:
            return handle_get_profile(event, user_id)

        # POST /users/invite (teacher onboards a user without a league)
        if http_method == 'POST' and '/users/invite' in path:
            return handle_invite_user(event, user_id)

        # POST /league/join
        if http_method == 'POST' and path.endswith('/league/join'):
            return handle_join(event, user_id)

        # POST /league/{leagueId}/invite (teacher invites student)
        if http_method == 'POST' and '/invite' in path:
            return handle_invite_student(event, user_id)

        # POST /league (create)
        if http_method == 'POST' and path.endswith('/league'):
            return handle_create(event, user_id)

        # GET /league/{leagueId}/leaderboard
        if http_method == 'GET' and '/leaderboard' in path:
            return handle_get_leaderboard(event, user_id)

        # GET /league/{leagueId}/members
        if http_method == 'GET' and '/members' in path:
            return handle_get_members(event, user_id)

        # DELETE /league/{leagueId}/members/{memberId}
        if http_method == 'DELETE' and '/members/' in path:
            return handle_remove_member(event, user_id)

        # GET /league/{leagueId}
        if http_method == 'GET':
            return handle_get_league(event, user_id)

        # PUT /league/{leagueId}
        if http_method == 'PUT':
            return handle_update_league(event, user_id)

        # DELETE /league/{leagueId}
        if http_method == 'DELETE':
            return handle_delete_league(event, user_id)

        return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in league handler: {e}")
        return build_error_response(e, 'league_handler')


def _generate_join_code():
    """Generate a random 6-character uppercase alphanumeric join code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _is_teacher(event):
    """Check if the caller is in the 'teachers' Cognito group."""
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    groups = claims.get('cognito:groups', '')
    # Groups come as a comma-separated string or may be a single value
    if isinstance(groups, str):
        return 'teachers' in [g.strip() for g in groups.split(',')]
    return False


def _get_user(user_id):
    """Get user record from Users table."""
    table = dynamodb.Table(USERS_TABLE)
    response = table.get_item(Key={'userId': user_id})
    return response.get('Item')


def _is_member_or_teacher(league_id, user_id):
    """Check if a user is a member of a league or the league's teacher."""
    league = _get_league(league_id)
    if league and league.get('teacherUserId') == user_id:
        return True
    table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    response = table.get_item(Key={'leagueId': league_id, 'userId': user_id})
    return response.get('Item') is not None


def _is_member(league_id, user_id):
    """Check if a user is a student member of a league."""
    table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    response = table.get_item(Key={'leagueId': league_id, 'userId': user_id})
    return response.get('Item') is not None


def _get_league(league_id):
    """Get league record."""
    table = dynamodb.Table(LEAGUES_TABLE)
    response = table.get_item(Key={'leagueId': league_id})
    return response.get('Item')


def handle_get_profile(event, user_id):
    """Handle GET /users/profile - Return the user's stored profile.

    Returns the displayName persisted in the Users table (empty string if the
    user has not set one yet).
    """
    user = _get_user(user_id)
    display_name = (user or {}).get('displayName', '') or ''
    return build_response(200, {'displayName': display_name})


def handle_update_profile(event, user_id):
    """Handle PUT /users/profile - Update user's display name.

    Expected body:
    {
        "displayName": "Max M."
    }
    """
    body = parse_body(event)
    display_name = body.get('displayName', '').strip()

    if not display_name:
        return build_response(400, {'error': 'displayName is required'})

    if len(display_name) > 50:
        return build_response(400, {'error': 'displayName must be 50 characters or less'})

    # Update Users table
    users_table = dynamodb.Table(USERS_TABLE)
    users_table.update_item(
        Key={'userId': user_id},
        UpdateExpression='SET displayName = :name',
        ExpressionAttributeValues={':name': display_name}
    )

    # Also update displayName in LeagueMembers if user is in a league
    user = _get_user(user_id)
    if user and user.get('leagueId'):
        members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
        try:
            members_table.update_item(
                Key={'leagueId': user['leagueId'], 'userId': user_id},
                UpdateExpression='SET displayName = :name',
                ExpressionAttributeValues={':name': display_name}
            )
        except Exception as e:
            logger.warning(f"Failed to update displayName in league members: {e}")

    return build_response(200, {'displayName': display_name})


def _validate_email(email):
    """Return a normalized email or None if invalid."""
    email = (email or '').strip().lower()
    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return None
    return email


def _create_or_get_cognito_user(email, display_name):
    """Create a Cognito user (invite email + temp password) or fetch existing.

    Also upserts the Users table record (without touching leagueId).

    Returns:
        tuple (new_user_id, error_response). On success error_response is None.
    """
    if not USER_POOL_ID:
        return None, build_response(500, {'error': 'User pool not configured'})

    new_user_id = None
    try:
        cognito_response = cognito_client.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'email_verified', 'Value': 'true'},
            ],
            DesiredDeliveryMediums=['EMAIL'],
        )
        for attr in cognito_response['User']['Attributes']:
            if attr['Name'] == 'sub':
                new_user_id = attr['Value']
                break
        if not new_user_id:
            return None, build_response(500, {'error': 'Failed to get user ID from Cognito'})

    except cognito_client.exceptions.UsernameExistsException:
        # User already exists — look up their sub
        try:
            existing = cognito_client.admin_get_user(
                UserPoolId=USER_POOL_ID,
                Username=email,
            )
            for attr in existing['UserAttributes']:
                if attr['Name'] == 'sub':
                    new_user_id = attr['Value']
                    break
            if not new_user_id:
                return None, build_response(500, {'error': 'Failed to get existing user ID'})
        except Exception as e:
            logger.exception(f"Failed to look up existing user: {e}")
            return None, build_response(500, {'error': 'Fehler beim Suchen des bestehenden Nutzers'})

    except Exception as e:
        logger.exception(f"Failed to create Cognito user: {e}")
        return None, build_response(500, {'error': f'Fehler beim Erstellen des Kontos: {str(e)}'})

    # Upsert Users record (do NOT change leagueId here)
    timestamp = get_timestamp()
    users_table = dynamodb.Table(USERS_TABLE)
    users_table.update_item(
        Key={'userId': new_user_id},
        UpdateExpression='SET displayName = if_not_exists(displayName, :dn), createdAt = if_not_exists(createdAt, :ts)',
        ExpressionAttributeValues={
            ':dn': display_name or email.split('@')[0],
            ':ts': timestamp,
        }
    )

    return new_user_id, None


def handle_invite_user(event, user_id):
    """Handle POST /users/invite - Teacher onboards a new user WITHOUT a league.

    Creates (or reuses) a Cognito account so a teacher can onboard students
    before starting a league. Cognito sends an invite email with a temporary
    password.

    Expected body: { "email": "...", "displayName": "..." (optional) }
    """
    if not _is_teacher(event):
        return build_response(403, {'error': 'Nur Lehrkräfte können Nutzer einladen'})

    body = parse_body(event)
    email = _validate_email(body.get('email'))
    if not email:
        return build_response(400, {'error': 'Ungültige E-Mail-Adresse'})
    display_name = body.get('displayName', '').strip()

    new_user_id, err = _create_or_get_cognito_user(email, display_name)
    if err:
        return err

    logger.info(json.dumps({
        'event': 'user_invited',
        'newUserId': new_user_id,
        'invitedBy': user_id,
    }))

    return build_response(201, {
        'userId': new_user_id,
        'displayName': display_name or email.split('@')[0],
        'message': 'Einladung wurde gesendet',
    })


def handle_invite_student(event, user_id):
    """Handle POST /league/{leagueId}/invite - Teacher creates a student account
    and adds them to the league.

    Expected body:
    {
        "email": "student@example.com",
        "displayName": "Max M."  (optional)
    }
    """
    if not _is_teacher(event):
        return build_response(403, {'error': 'Only teachers can invite students'})

    league_id = get_path_parameter(event, 'leagueId')

    league = _get_league(league_id)
    if not league:
        return build_response(404, {'error': 'League not found'})

    if league['teacherUserId'] != user_id:
        return build_response(403, {'error': 'Only the league teacher can invite students'})

    body = parse_body(event)
    email = _validate_email(body.get('email'))
    if not email:
        return build_response(400, {'error': 'Ungültige E-Mail-Adresse'})
    display_name = body.get('displayName', '').strip()

    new_user_id, err = _create_or_get_cognito_user(email, display_name)
    if err:
        return err

    # Assign the league to the user
    timestamp = get_timestamp()
    users_table = dynamodb.Table(USERS_TABLE)
    users_table.update_item(
        Key={'userId': new_user_id},
        UpdateExpression='SET leagueId = :lid',
        ExpressionAttributeValues={':lid': league_id},
    )

    # Add as league member (skip if already member)
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    existing_member = members_table.get_item(
        Key={'leagueId': league_id, 'userId': new_user_id}
    )
    if not existing_member.get('Item'):
        members_table.put_item(Item={
            'leagueId': league_id,
            'userId': new_user_id,
            'displayName': display_name or email.split('@')[0],
            'role': 'student',
            'currentStreak': 0,
            'totalCorrect': 0,
            'totalAttempts': 0,
            'weeklyCorrect': 0,
            'weekStartDate': '',
            'lastPracticeDate': '',
            'joinedAt': timestamp,
        })

    logger.info(json.dumps({
        'event': 'student_invited',
        'leagueId': league_id,
        'newUserId': new_user_id,
        'invitedBy': user_id,
    }))

    return build_response(201, {
        'userId': new_user_id,
        'displayName': display_name or email.split('@')[0],
        'message': 'Einladung wurde gesendet',
    })


def handle_create(event, user_id):
    """Handle POST /league - Teacher creates a league.

    Expected body:
    {
        "name": "Klasse 9b Französisch",
        "scoreMode": "weekly"  (optional, default "weekly")
    }
    """
    # Check user is a teacher (via Cognito group)
    if not _is_teacher(event):
        return build_response(403, {'error': 'Only teachers can create leagues'})

    # Get or create user record
    user = _get_user(user_id)
    if not user:
        # Create minimal user record if it doesn't exist yet
        users_table = dynamodb.Table(USERS_TABLE)
        user = {'userId': user_id, 'role': 'teacher'}
        users_table.put_item(Item=user)

    body = parse_body(event)
    name = body.get('name', '').strip()
    if not name:
        return build_response(400, {'error': 'League name is required'})

    score_mode = body.get('scoreMode', 'weekly')
    if score_mode not in ('total', 'weekly', 'accuracy', 'combined'):
        return build_response(400, {'error': 'Invalid scoreMode. Must be one of: total, weekly, accuracy, combined'})

    league_id = generate_uuid()
    join_code = _generate_join_code()
    timestamp = get_timestamp()

    # Create league record
    leagues_table = dynamodb.Table(LEAGUES_TABLE)
    league_item = {
        'leagueId': league_id,
        'name': name,
        'teacherUserId': user_id,
        'joinCode': join_code,
        'scoreMode': score_mode,
        'vocabSetIds': [],
        'createdAt': timestamp,
        'updatedAt': timestamp,
    }
    leagues_table.put_item(Item=league_item)

    # Update teacher's user record with leagueId (for quick lookup)
    users_table = dynamodb.Table(USERS_TABLE)
    users_table.update_item(
        Key={'userId': user_id},
        UpdateExpression='SET leagueId = :lid',
        ExpressionAttributeValues={':lid': league_id}
    )

    logger.info(json.dumps({
        'event': 'league_created',
        'leagueId': league_id,
        'teacherUserId': user_id,
    }))

    return build_response(201, league_item)


def handle_join(event, user_id):
    """Handle POST /league/join - Student joins a league.

    Expected body:
    {
        "joinCode": "ABC123"
    }
    """
    body = parse_body(event)
    join_code = body.get('joinCode', '').strip().upper()

    if not join_code:
        return build_response(400, {'error': 'joinCode is required'})

    # Check if user is already in a league
    user = _get_user(user_id)
    if not user:
        # User record doesn't exist yet (first interaction) - create it
        users_table = dynamodb.Table(USERS_TABLE)
        user = {'userId': user_id, 'role': 'student'}
        users_table.put_item(Item=user)

    if user.get('leagueId'):
        return build_response(400, {'error': 'You are already in a league. Leave your current league first.'})

    # Find league by join code
    leagues_table = dynamodb.Table(LEAGUES_TABLE)
    response = leagues_table.query(
        IndexName='joinCode-index',
        KeyConditionExpression=Key('joinCode').eq(join_code)
    )

    items = response.get('Items', [])
    if not items:
        return build_response(404, {'error': 'Invalid join code. No league found.'})

    league = items[0]
    league_id = league['leagueId']

    # Check user is not already a member
    if _is_member(league_id, user_id):
        return build_response(400, {'error': 'You are already a member of this league'})

    # Add member
    timestamp = get_timestamp()
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    members_table.put_item(Item={
        'leagueId': league_id,
        'userId': user_id,
        'displayName': user.get('displayName', 'Unbekannt'),
        'role': 'student',
        'currentStreak': 0,
        'totalCorrect': 0,
        'totalAttempts': 0,
        'weeklyCorrect': 0,
        'weekStartDate': '',
        'lastPracticeDate': '',
        'joinedAt': timestamp,
    })

    # Update user record with leagueId
    users_table = dynamodb.Table(USERS_TABLE)
    users_table.update_item(
        Key={'userId': user_id},
        UpdateExpression='SET leagueId = :lid',
        ExpressionAttributeValues={':lid': league_id}
    )

    logger.info(json.dumps({
        'event': 'league_joined',
        'leagueId': league_id,
        'userId': user_id,
    }))

    return build_response(200, {
        'leagueId': league_id,
        'name': league['name'],
        'joinCode': league['joinCode'],
        'scoreMode': league.get('scoreMode', 'weekly'),
    })


def handle_get_league(event, user_id):
    """Handle GET /league/{leagueId} - Get league details."""
    league_id = get_path_parameter(event, 'leagueId')

    # Verify membership
    if not _is_member_or_teacher(league_id, user_id):
        return build_response(403, {'error': 'You are not a member of this league'})

    league = _get_league(league_id)
    if not league:
        return build_response(404, {'error': 'League not found'})

    # Get caller's member stats
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    member_response = members_table.get_item(Key={'leagueId': league_id, 'userId': user_id})
    member = member_response.get('Item', {})

    return build_response(200, {
        'league': league,
        'memberStats': member,
    })


def handle_update_league(event, user_id):
    """Handle PUT /league/{leagueId} - Teacher updates league settings.

    Expected body (all optional):
    {
        "name": "New name",
        "scoreMode": "total",
        "vocabSetIds": ["uuid1", "uuid2"]
    }
    """
    league_id = get_path_parameter(event, 'leagueId')

    league = _get_league(league_id)
    if not league:
        return build_response(404, {'error': 'League not found'})

    if league['teacherUserId'] != user_id:
        return build_response(403, {'error': 'Only the league teacher can update settings'})

    body = parse_body(event)
    timestamp = get_timestamp()

    update_parts = ['updatedAt = :ts']
    expr_values = {':ts': timestamp}

    if 'name' in body:
        name = body['name'].strip()
        if not name:
            return build_response(400, {'error': 'League name cannot be empty'})
        update_parts.append('#n = :name')
        expr_values[':name'] = name

    if 'scoreMode' in body:
        score_mode = body['scoreMode']
        if score_mode not in ('total', 'weekly', 'accuracy', 'combined'):
            return build_response(400, {'error': 'Invalid scoreMode'})
        update_parts.append('scoreMode = :sm')
        expr_values[':sm'] = score_mode

    if 'vocabSetIds' in body:
        vocab_set_ids = body['vocabSetIds']
        if not isinstance(vocab_set_ids, list):
            return build_response(400, {'error': 'vocabSetIds must be a list'})
        update_parts.append('vocabSetIds = :vs')
        expr_values[':vs'] = vocab_set_ids

    update_expr = 'SET ' + ', '.join(update_parts)
    expr_names = {}
    if '#n' in update_expr:
        expr_names['#n'] = 'name'

    leagues_table = dynamodb.Table(LEAGUES_TABLE)
    kwargs = {
        'Key': {'leagueId': league_id},
        'UpdateExpression': update_expr,
        'ExpressionAttributeValues': expr_values,
        'ReturnValues': 'ALL_NEW',
    }
    if expr_names:
        kwargs['ExpressionAttributeNames'] = expr_names

    response = leagues_table.update_item(**kwargs)

    logger.info(json.dumps({
        'event': 'league_updated',
        'leagueId': league_id,
        'userId': user_id,
    }))

    return build_response(200, response.get('Attributes', {}))


def handle_delete_league(event, user_id):
    """Handle DELETE /league/{leagueId} - Teacher deletes the league."""
    league_id = get_path_parameter(event, 'leagueId')

    league = _get_league(league_id)
    if not league:
        return build_response(404, {'error': 'League not found'})

    if league['teacherUserId'] != user_id:
        return build_response(403, {'error': 'Only the league teacher can delete the league'})

    # Get all members
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    response = members_table.query(
        KeyConditionExpression=Key('leagueId').eq(league_id)
    )
    members = response.get('Items', [])

    # Clear leagueId from all member Users records
    users_table = dynamodb.Table(USERS_TABLE)
    for member in members:
        try:
            users_table.update_item(
                Key={'userId': member['userId']},
                UpdateExpression='REMOVE leagueId',
            )
        except Exception as e:
            logger.warning(f"Failed to clear leagueId for user {member['userId']}: {e}")

    # Batch delete all members
    with members_table.batch_writer() as batch:
        for member in members:
            batch.delete_item(Key={
                'leagueId': league_id,
                'userId': member['userId'],
            })

    # Delete league
    leagues_table = dynamodb.Table(LEAGUES_TABLE)
    leagues_table.delete_item(Key={'leagueId': league_id})

    logger.info(json.dumps({
        'event': 'league_deleted',
        'leagueId': league_id,
        'userId': user_id,
    }))

    return build_response(200, {'message': 'League deleted successfully'})


def handle_get_leaderboard(event, user_id):
    """Handle GET /league/{leagueId}/leaderboard - Get ranked leaderboard."""
    league_id = get_path_parameter(event, 'leagueId')

    # Verify membership or teacher
    if not _is_member_or_teacher(league_id, user_id):
        return build_response(403, {'error': 'You are not a member of this league'})

    league = _get_league(league_id)
    if not league:
        return build_response(404, {'error': 'League not found'})

    score_mode = league.get('scoreMode', 'weekly')

    # Get all members (exclude the teacher — they manage, not compete)
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    response = members_table.query(
        KeyConditionExpression=Key('leagueId').eq(league_id)
    )
    teacher_id = league.get('teacherUserId', '')
    members = [m for m in response.get('Items', []) if m.get('userId') != teacher_id and m.get('role') != 'teacher']

    # Calculate current week Monday (Europe/Berlin approx UTC+2)
    now_berlin = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    monday = (now_berlin - datetime.timedelta(days=now_berlin.weekday())).strftime('%Y-%m-%d')

    # Calculate scores based on scoreMode
    scored_members = []
    for member in members:
        total_correct = int(member.get('totalCorrect', 0))
        total_attempts = int(member.get('totalAttempts', 0))
        weekly_correct = int(member.get('weeklyCorrect', 0))
        current_streak = int(member.get('currentStreak', 0))
        week_start_date = member.get('weekStartDate', '')

        # Reset weekly if not current week
        if week_start_date != monday:
            weekly_correct = 0

        if score_mode == 'total':
            score = total_correct
        elif score_mode == 'weekly':
            score = weekly_correct
        elif score_mode == 'accuracy':
            score = round(total_correct / max(total_attempts, 1) * 100, 1)
        elif score_mode == 'combined':
            score = round(total_correct * max(1, current_streak / 7), 1)
        else:
            score = weekly_correct

        scored_members.append({
            'userId': member['userId'],
            'displayName': member.get('displayName', 'Unknown'),
            'score': score,
            'currentStreak': current_streak,
            'role': member.get('role', 'student'),
        })

    # Sort descending by score
    scored_members.sort(key=lambda x: x['score'], reverse=True)

    # Add rank
    for i, m in enumerate(scored_members):
        m['rank'] = i + 1

    return build_response(200, {
        'leagueId': league_id,
        'scoreMode': score_mode,
        'leaderboard': scored_members,
    })


def handle_get_members(event, user_id):
    """Handle GET /league/{leagueId}/members - Teacher gets all members with stats."""
    league_id = get_path_parameter(event, 'leagueId')

    league = _get_league(league_id)
    if not league:
        return build_response(404, {'error': 'League not found'})

    if league['teacherUserId'] != user_id:
        return build_response(403, {'error': 'Only the league teacher can view all member details'})

    # Get all members
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    response = members_table.query(
        KeyConditionExpression=Key('leagueId').eq(league_id)
    )
    members = response.get('Items', [])

    return build_response(200, {
        'leagueId': league_id,
        'members': members,
    })


def handle_remove_member(event, user_id):
    """Handle DELETE /league/{leagueId}/members/{memberId} - Teacher removes a member."""
    league_id = get_path_parameter(event, 'leagueId')
    member_id = get_path_parameter(event, 'memberId')

    league = _get_league(league_id)
    if not league:
        return build_response(404, {'error': 'League not found'})

    if league['teacherUserId'] != user_id:
        return build_response(403, {'error': 'Only the league teacher can remove members'})

    if member_id == user_id:
        return build_response(400, {'error': 'Cannot remove yourself. Delete the league instead.'})

    # Delete member
    members_table = dynamodb.Table(LEAGUE_MEMBERS_TABLE)
    members_table.delete_item(Key={
        'leagueId': league_id,
        'userId': member_id,
    })

    # Clear leagueId from user
    users_table = dynamodb.Table(USERS_TABLE)
    users_table.update_item(
        Key={'userId': member_id},
        UpdateExpression='REMOVE leagueId',
    )

    logger.info(json.dumps({
        'event': 'member_removed',
        'leagueId': league_id,
        'memberId': member_id,
        'removedBy': user_id,
    }))

    return build_response(200, {'message': 'Member removed successfully'})
