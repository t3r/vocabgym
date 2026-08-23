"""Invite Handler - Generate and validate invite links for VocabGym."""

import json
import logging
import os
import hmac
import hashlib
import base64
import time

from lib.utils import (
    build_response,
    build_error_response,
    get_user_id_from_event,
    get_path_parameter,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

INVITE_SECRET = os.environ.get('INVITE_SECRET', 'vocabgym-default-invite-secret-change-me')
INVITE_EXPIRY_SECONDS = 7 * 24 * 60 * 60  # 7 days
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')


def lambda_handler(event, context):
    """Route invite requests.

    Routes:
    - POST /invite (authenticated): Generate a new invite link
    - GET /invite/{token} (public): Validate an invite token
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    logger.info(json.dumps({
        'event': 'invite_request',
        'httpMethod': http_method,
        'path': path,
    }))

    try:
        if http_method == 'POST':
            user_id = get_user_id_from_event(event)
            return handle_create_invite(event, user_id)
        elif http_method == 'GET':
            return handle_validate_invite(event)
        else:
            return build_response(404, {'error': 'Not found'})

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return build_response(400, {'error': str(e)})

    except Exception as e:
        logger.exception(f"Unexpected error in invite handler: {e}")
        return build_error_response(e, 'invite_handler')


def handle_create_invite(event, user_id):
    """Handle POST /invite - Generate a new invite link.

    Returns:
    {
        "inviteUrl": "https://vocabgym.../invite/TOKEN",
        "expiresAt": 1234567890,
        "expiresIn": "7 Tage"
    }
    """
    created_at = int(time.time())
    expires_at = created_at + INVITE_EXPIRY_SECONDS

    # Create token payload: userId:timestamp
    payload = f"{user_id}:{created_at}"

    # Sign with HMAC-SHA256
    signature = hmac.new(
        INVITE_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:16]  # Use first 16 chars of hex digest for shorter URL

    # Token format: base64url(payload:signature)
    token_data = f"{payload}:{signature}"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    invite_url = f"{FRONTEND_URL}/invite/{token}"

    logger.info(json.dumps({
        'event': 'invite_created',
        'userId': user_id,
        'expiresAt': expires_at,
    }))

    return build_response(200, {
        'inviteUrl': invite_url,
        'token': token,
        'expiresAt': expires_at,
        'expiresIn': '7 Tage',
    })


def handle_validate_invite(event):
    """Handle GET /invite/{token} - Validate an invite token.

    Returns:
    {
        "valid": true/false,
        "expired": true/false,
        "message": "..."
    }
    """
    token = get_path_parameter(event, 'token')

    # Decode token
    try:
        # Add padding back
        padded = token + '=' * (4 - len(token) % 4) if len(token) % 4 else token
        token_data = base64.urlsafe_b64decode(padded.encode('utf-8')).decode('utf-8')
    except Exception:
        return build_response(200, {
            'valid': False,
            'expired': False,
            'message': 'Ungültiger Einladungslink.',
        })

    # Parse token: userId:timestamp:signature
    parts = token_data.split(':')
    if len(parts) != 3:
        return build_response(200, {
            'valid': False,
            'expired': False,
            'message': 'Ungültiger Einladungslink.',
        })

    user_id, timestamp_str, provided_signature = parts

    # Verify signature
    try:
        created_at = int(timestamp_str)
    except ValueError:
        return build_response(200, {
            'valid': False,
            'expired': False,
            'message': 'Ungültiger Einladungslink.',
        })

    payload = f"{user_id}:{timestamp_str}"
    expected_signature = hmac.new(
        INVITE_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:16]

    if not hmac.compare_digest(provided_signature, expected_signature):
        return build_response(200, {
            'valid': False,
            'expired': False,
            'message': 'Ungültiger Einladungslink.',
        })

    # Check expiry
    now = int(time.time())
    if now > created_at + INVITE_EXPIRY_SECONDS:
        return build_response(200, {
            'valid': False,
            'expired': True,
            'message': 'Dieser Einladungslink ist abgelaufen. Bitte frage nach einem neuen Link.',
        })

    return build_response(200, {
        'valid': True,
        'expired': False,
        'message': 'Du wurdest zu VocabGym eingeladen!',
    })
