"""JWT validation utilities for VocabTrainer."""

import json
import logging
import time
import urllib.request
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_jwks(user_pool_id, region):
    """Fetch and cache the JWKS (JSON Web Key Set) from Cognito.

    Args:
        user_pool_id: Cognito User Pool ID
        region: AWS region

    Returns:
        dict: JWKS document
    """
    jwks_url = (
        f"https://cognito-idp.{region}.amazonaws.com/"
        f"{user_pool_id}/.well-known/jwks.json"
    )
    try:
        with urllib.request.urlopen(jwks_url, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        raise


def validate_token_claims(claims, user_pool_id, client_id):
    """Validate JWT token claims.

    Note: In production, API Gateway with Cognito authorizer handles
    full JWT validation. This function provides additional claim checks
    if needed within Lambda functions.

    Args:
        claims: Decoded JWT claims dict
        user_pool_id: Expected Cognito User Pool ID
        client_id: Expected client ID

    Returns:
        bool: True if claims are valid

    Raises:
        ValueError: If claims are invalid
    """
    # Check token expiration
    exp = claims.get('exp')
    if exp and int(exp) < int(time.time()):
        raise ValueError("Token has expired")

    # Check issuer
    expected_issuer = f"https://cognito-idp.{claims.get('iss', '').split('/')[-2] if '/' in claims.get('iss', '') else ''}.amazonaws.com/{user_pool_id}"
    if claims.get('iss') and claims['iss'] != expected_issuer:
        logger.warning(f"Token issuer mismatch: {claims.get('iss')}")

    # Check token use
    token_use = claims.get('token_use')
    if token_use and token_use not in ('id', 'access'):
        raise ValueError(f"Invalid token_use: {token_use}")

    return True


def get_user_email_from_claims(event):
    """Extract user email from Cognito claims.

    Args:
        event: API Gateway Lambda proxy event

    Returns:
        str or None: User email if available
    """
    try:
        claims = event['requestContext']['authorizer']['claims']
        return claims.get('email')
    except (KeyError, TypeError):
        return None


def get_user_name_from_claims(event):
    """Extract user display name from Cognito claims.

    Args:
        event: API Gateway Lambda proxy event

    Returns:
        str or None: User name if available
    """
    try:
        claims = event['requestContext']['authorizer']['claims']
        return claims.get('cognito:username') or claims.get('email')
    except (KeyError, TypeError):
        return None
