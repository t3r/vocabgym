"""Per-user cache for AI-generated learning tips.

Generating tips calls an LLM, so we must NOT do it on every /progress/overview
request. This caches one row per user in DynamoDB and only regenerates when:
  - there is no cached row (cache miss), OR
  - the user's error fingerprint changed (different weak-word mistakes), OR
  - the cached row has expired (TTL).

The fingerprint is a hash over the *classified clusters* (types + the target
words in each), so tips are refreshed exactly when the underlying mistakes
change — not on unrelated activity.
"""

import hashlib
import json
import logging
import os
import time

import boto3

logger = logging.getLogger()

dynamodb = boto3.resource('dynamodb')
LEARNING_TIPS_TABLE = os.environ.get('LEARNING_TIPS_TABLE', '')

# Refresh at most weekly even if the fingerprint is unchanged (keeps phrasing
# fresh and lets prompt/model improvements roll out).
TTL_SECONDS = 7 * 24 * 60 * 60


def fingerprint(clusters):
    """Stable hash of the error clusters (type + target words), order-independent
    within a cluster's words but preserving cluster identity."""
    sig = []
    for c in clusters or []:
        words = sorted((w.get('target', '') for w in c.get('words', [])))
        sig.append({'type': c.get('type'), 'words': words})
    raw = json.dumps(sig, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def get_cached(user_id, expected_fingerprint):
    """Return cached tips list if present, unexpired and matching the
    fingerprint; else None.
    """
    if not LEARNING_TIPS_TABLE or not user_id:
        return None
    try:
        table = dynamodb.Table(LEARNING_TIPS_TABLE)
        item = table.get_item(Key={'userId': user_id}).get('Item')
        if not item:
            return None
        if item.get('fingerprint') != expected_fingerprint:
            return None
        # Respect TTL even before DynamoDB physically deletes the row.
        expires_at = int(item.get('expiresAt', 0) or 0)
        if expires_at and expires_at < int(time.time()):
            return None
        tips = item.get('tips')
        return tips if isinstance(tips, list) else None
    except Exception as e:
        logger.warning(json.dumps({'event': 'learning_tips_cache_read_failed', 'error': str(e)}))
        return None


def put_cached(user_id, fp, tips):
    """Persist tips for a user with the given fingerprint + TTL. Best-effort."""
    if not LEARNING_TIPS_TABLE or not user_id:
        return
    try:
        table = dynamodb.Table(LEARNING_TIPS_TABLE)
        table.put_item(Item={
            'userId': user_id,
            'fingerprint': fp,
            'tips': tips,
            'updatedAt': int(time.time()),
            'expiresAt': int(time.time()) + TTL_SECONDS,
        })
    except Exception as e:
        logger.warning(json.dumps({'event': 'learning_tips_cache_write_failed', 'error': str(e)}))


def get_or_generate(user_id, clusters, generate_fn):
    """Return tips for the user: from cache when fresh, else generate + cache.

    Args:
        user_id: the learner's id (cache key).
        clusters: error clusters from build_error_clusters (may be empty).
        generate_fn: callable(clusters) -> list of tips (the LLM path).

    Returns: list of tip dicts (possibly empty when there are no clusters).
    """
    if not clusters:
        return []
    fp = fingerprint(clusters)
    cached = get_cached(user_id, fp)
    if cached is not None:
        logger.info(json.dumps({'event': 'learning_tips_cache_hit'}))
        return cached
    tips = generate_fn(clusters) or []
    if tips:
        put_cached(user_id, fp, tips)
    return tips
