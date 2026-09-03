"""Tests for LLM-phrased learning tips (progress_handler/learning_tips.py).

The Bedrock client is mocked: we verify parsing, cluster tagging, and — crucially
— that every failure mode (guardrail block, bad JSON, Bedrock error) degrades
gracefully to the deterministic rule-based fallback tips.
"""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'functions', 'progress_handler'))

import learning_tips as lt
from lib import error_clusters as ec


def _clusters():
    weak = [
        {'source': 'ein Netz', 'target': 'un réseau', 'recentErrors': ['un resau']},
        {'source': 'ein soziales Netzwerk', 'target': 'un réseau social',
         'recentErrors': ['un resau social']},
        {'source': 'eine Nachricht', 'target': 'une nouvelle', 'recentErrors': ['un nouvelle']},
        {'source': 'ein Journalist', 'target': 'un journaliste', 'recentErrors': ['un journalist']},
    ]
    return ec.build_error_clusters(weak, 'fr')


def _mock_response(text):
    return {'output': {'message': {'content': [{'text': text}]}}}


def test_empty_clusters_returns_empty(monkeypatch):
    # No LLM call should even happen.
    called = MagicMock()
    monkeypatch.setattr(lt.bedrock_client, 'converse', called)
    assert lt.generate_tips([]) == []
    called.assert_not_called()


def test_happy_path_parses_and_tags_clusters(monkeypatch):
    clusters = _clusters()
    llm_json = json.dumps([
        {'title': 'Genus merken', 'body': 'Lerne das Wort mit Artikel.'},
        {'title': 'eau klingt wie o', 'body': 'un réseau, des réseaux.'},
        {'title': 'Falscher Freund', 'body': 'un journaliste mit -e.'},
    ])
    monkeypatch.setattr(lt.bedrock_client, 'converse',
                        lambda **kw: _mock_response(llm_json))

    tips = lt.generate_tips(clusters)
    assert len(tips) >= 1
    assert tips[0]['title'] and tips[0]['body']
    # Each tip is tagged with the corresponding cluster type (by order).
    assert tips[0]['cluster'] == clusters[0]['type']


def test_markdown_fenced_json_is_parsed(monkeypatch):
    clusters = _clusters()
    fenced = "```json\n" + json.dumps([{'title': 'T', 'body': 'B'}]) + "\n```"
    monkeypatch.setattr(lt.bedrock_client, 'converse',
                        lambda **kw: _mock_response(fenced))
    tips = lt.generate_tips(clusters)
    assert tips[0]['title'] == 'T' and tips[0]['body'] == 'B'


def test_guardrail_block_falls_back(monkeypatch):
    clusters = _clusters()
    monkeypatch.setattr(lt.bedrock_client, 'converse',
                        lambda **kw: {'stopReason': 'guardrail_intervened'})
    tips = lt.generate_tips(clusters)
    # Fallback tips come from the rule-based library and are non-empty.
    assert len(tips) >= 1
    assert all(t['title'] and t['body'] and t.get('cluster') for t in tips)


def test_bad_json_falls_back(monkeypatch):
    clusters = _clusters()
    monkeypatch.setattr(lt.bedrock_client, 'converse',
                        lambda **kw: _mock_response('not json at all'))
    tips = lt.generate_tips(clusters)
    assert len(tips) >= 1  # graceful fallback, not a crash


def test_bedrock_exception_falls_back(monkeypatch):
    clusters = _clusters()
    def boom(**kw):
        raise RuntimeError('bedrock down')
    monkeypatch.setattr(lt.bedrock_client, 'converse', boom)
    tips = lt.generate_tips(clusters)
    assert len(tips) >= 1


def test_empty_llm_list_falls_back(monkeypatch):
    clusters = _clusters()
    monkeypatch.setattr(lt.bedrock_client, 'converse',
                        lambda **kw: _mock_response('[]'))
    tips = lt.generate_tips(clusters)
    # Empty usable entries -> fallback
    assert len(tips) >= 1


def test_prompt_contains_no_user_identifiers(monkeypatch):
    # The prompt must only carry error types + target words, never names/ids.
    clusters = _clusters()
    captured = {}
    def capture(**kw):
        captured['kw'] = kw
        return _mock_response('[{"title":"T","body":"B"}]')
    monkeypatch.setattr(lt.bedrock_client, 'converse', capture)
    lt.generate_tips(clusters)
    sent = json.dumps(captured['kw'], ensure_ascii=False)
    assert 'progressKey' not in sent and 'userId' not in sent
