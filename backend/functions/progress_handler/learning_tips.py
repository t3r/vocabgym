"""Turn rule-based error clusters into short, warm German learning tips.

The *analysis* (which mistakes group together) is done deterministically in
error_clusters.py. Here an LLM (Amazon Nova Lite by default) only *phrases* the
tips — it never decides what is wrong. That keeps the advice cheap, fast and
factually anchored, and lets us fall back to the curated per-cluster tips
whenever the model is unavailable or returns something unusable.

Design notes:
- Model is env-configurable (LEARNING_TIPS_MODEL_ID), defaulting to the EU
  Nova Lite inference profile so learner data stays in-region (eu-central-1).
- The Bedrock guardrail (shared with extraction) is applied when configured.
- Output is strictly validated; ANY problem => rule-based fallback_tips().
"""

import json
import logging
import os

import boto3

from lib.error_clusters import fallback_tips

logger = logging.getLogger()

bedrock_client = boto3.client('bedrock-runtime')

# EU Nova Lite inference profile — small/fast/cheap, enough for phrasing.
MODEL_ID = os.environ.get('LEARNING_TIPS_MODEL_ID', 'eu.amazon.nova-lite-v1:0')
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID', '')
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', '')

MAX_TIPS = 3


def _guardrail_config():
    if GUARDRAIL_ID and GUARDRAIL_VERSION:
        return {
            'guardrailIdentifier': GUARDRAIL_ID,
            'guardrailVersion': GUARDRAIL_VERSION,
            'trace': 'enabled',
        }
    return None


def _build_prompt(clusters):
    """Build the instruction + a compact JSON description of the clusters."""
    # Only send what the model needs: type, and up to 3 example target words per
    # cluster (never user identifiers).
    compact = []
    for c in clusters[:MAX_TIPS]:
        compact.append({
            'fehlertyp': c['type'],
            'beispiele': [w['target'] for w in c['words'][:3]],
            'anzahl_woerter': c['wordCount'],
        })

    instruction = (
        "Du bist ein freundlicher Französisch-Lerncoach für deutsche "
        "Gymnasiast:innen. Du bekommst Gruppen von Fehlern, die ein:e Schüler:in "
        "aktuell macht (je Gruppe ein Fehlertyp und ein paar französische "
        "Beispielwörter). Formuliere für JEDE Gruppe genau EINEN kurzen, "
        "motivierenden Lerntipp auf Deutsch, in der Du-Form.\n\n"
        "Regeln:\n"
        "- Jeder Tipp: ein knackiger Titel (max. 6 Wörter) und 1–2 Sätze Text.\n"
        "- Konkret und korrekt: nenne die Regel und nutze die Beispielwörter.\n"
        "- Freundlich, nie herabsetzend. Keine Emojis im Titel.\n"
        "- Kein Fließtext drumherum, KEIN Markdown.\n"
        "Antworte NUR mit einem JSON-Array dieser Form:\n"
        '[{"title": "…", "body": "…"}]\n'
    )
    data = json.dumps({'fehlergruppen': compact}, ensure_ascii=False)
    return instruction, data


def _converse(instruction_text, guarded_text, max_tokens=600):
    content = [
        {'text': instruction_text},
        {'guardContent': {'text': {'text': guarded_text, 'qualifiers': ['guard_content']}}},
    ]
    kwargs = {
        'modelId': MODEL_ID,
        'messages': [{'role': 'user', 'content': content}],
        'inferenceConfig': {'maxTokens': max_tokens, 'temperature': 0.4},
    }
    gc = _guardrail_config()
    if gc:
        kwargs['guardrailConfig'] = gc
    return bedrock_client.converse(**kwargs)


def _parse_tips(result_text):
    """Parse the model's JSON array into validated tip dicts. Raises on garbage."""
    text = (result_text or '').strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        text = text.rsplit('```', 1)[0]
    text = text.strip()
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError('LLM tips result is not a list')
    tips = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        title = str(item.get('title', '')).strip()
        body = str(item.get('body', '')).strip()
        if title and body:
            tips.append({'title': title[:80], 'body': body[:400]})
    if not tips:
        raise ValueError('LLM tips result had no usable entries')
    return tips[:MAX_TIPS]


def generate_tips(clusters):
    """Return up to MAX_TIPS learning tips for the given error clusters.

    Tries the LLM first; on ANY failure (no clusters aside, guardrail block,
    parse error, Bedrock error) returns the deterministic rule-based tips so the
    feature degrades gracefully and never breaks the progress overview.

    Returns: list of {'title','body','cluster'?}. Empty list if no clusters.
    """
    if not clusters:
        return []

    # Attach cluster type to the LLM tips by position (clusters are ordered and
    # we prompt for one tip per cluster, in order).
    cluster_types = [c['type'] for c in clusters[:MAX_TIPS]]

    try:
        instruction, data = _build_prompt(clusters)
        response = _converse(instruction, data)

        if response.get('stopReason') == 'guardrail_intervened':
            logger.warning(json.dumps({'event': 'learning_tips_guardrail_blocked'}))
            return fallback_tips(clusters, limit=MAX_TIPS)

        result_text = response['output']['message']['content'][0]['text']
        tips = _parse_tips(result_text)

        # Best-effort: tag each tip with the corresponding cluster type.
        for i, t in enumerate(tips):
            t['cluster'] = cluster_types[i] if i < len(cluster_types) else None

        logger.info(json.dumps({'event': 'learning_tips_generated', 'count': len(tips)}))
        return tips
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'learning_tips_fallback',
            'error': str(e),
            'errorType': type(e).__name__,
        }))
        return fallback_tips(clusters, limit=MAX_TIPS)
