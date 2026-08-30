"""Subscription plan limits and race-safe owned-set counting.

This module centralizes how many vocabulary sets a plan may own and provides
an atomic, race-condition-safe counter on the Users table so that concurrent
create requests cannot exceed a plan's set limit (TOCTOU protection).

The actual per-plan enforcement is enabled once the subscription `plan` field
exists on the Users record. Until then callers can pass a high/`None` limit so
the counter is maintained without blocking.
"""

import logging

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Owned-set limits per plan. None = unlimited.
PLAN_SET_LIMITS = {
    'free': 1,
    'student': 10,
    'teacher': None,   # unlimited
}

# Default plan when a user record has no explicit plan yet.
DEFAULT_PLAN = 'free'


def get_plan_set_limit(plan):
    """Return the owned-set limit for a plan (None = unlimited)."""
    return PLAN_SET_LIMITS.get(plan or DEFAULT_PLAN, PLAN_SET_LIMITS[DEFAULT_PLAN])


def try_reserve_set_slot(users_table, user_id, limit):
    """Atomically reserve one owned-set slot for the user.

    Performs a single conditional atomic increment of `ownedSetCount` on the
    Users table. This is race-safe: concurrent requests cannot both succeed
    past the limit because DynamoDB serializes the conditional update.

    Args:
        users_table: boto3 DynamoDB Table resource for the Users table.
        user_id: Cognito sub.
        limit: Max owned sets (int) or None for unlimited.

    Returns:
        bool: True if a slot was reserved (increment applied), False if the
              user is already at the limit.
    """
    # Unlimited plan: still maintain the counter, but never block.
    if limit is None:
        users_table.update_item(
            Key={'userId': user_id},
            UpdateExpression='ADD ownedSetCount :one',
            ExpressionAttributeValues={':one': 1},
        )
        return True

    try:
        users_table.update_item(
            Key={'userId': user_id},
            UpdateExpression='ADD ownedSetCount :one',
            # Allow when the attribute does not exist yet OR is below the limit.
            ConditionExpression='attribute_not_exists(ownedSetCount) OR ownedSetCount < :limit',
            ExpressionAttributeValues={':one': 1, ':limit': limit},
        )
        return True
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            logger.info(
                "Set limit reached for user %s (limit=%s)", user_id, limit
            )
            return False
        raise


def release_set_slot(users_table, user_id):
    """Atomically release one owned-set slot (on delete).

    Decrements `ownedSetCount` but never below zero.
    """
    try:
        users_table.update_item(
            Key={'userId': user_id},
            UpdateExpression='ADD ownedSetCount :neg',
            # Only decrement if the counter is currently > 0 to avoid going negative.
            ConditionExpression='attribute_exists(ownedSetCount) AND ownedSetCount > :zero',
            ExpressionAttributeValues={':neg': -1, ':zero': 0},
        )
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            # Counter already at 0 or missing — nothing to release.
            return
        raise
