"""Tests for rule-based error clustering (progress_handler/error_clusters.py).

Fixtures are taken from the REAL wrong answers of the affected learner, so the
classifier is pinned against actual mistake patterns, not invented ones.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'functions', 'progress_handler'))

import error_clusters as ec


# ---- noise filter ---------------------------------------------------------

def test_noise_is_filtered():
    for junk in ['', 'd', '?', '.', '  ', 'c', 'f', 'v']:
        assert ec.is_noise(junk, 'un réseau') is True


def test_real_attempt_is_not_noise():
    assert ec.is_noise('resau social', 'un réseau social') is False
    assert ec.is_noise('un journalist', 'un journaliste') is False


# ---- single-answer classification -----------------------------------------

def _articles_genders(lang='fr'):
    from lib.languages import get_all_articles, get_article_genders
    arts = set(ec._norm(a) for a in (get_all_articles(lang) or []))
    genders = set(ec._norm(a) for a in (get_article_genders(lang) or {}).keys())
    return arts, genders


def test_classify_phonetic_reseau():
    arts, genders = _articles_genders()
    # "resau" / "resaue" written the way réseau sounds.
    assert ec.classify_answer('un resau', 'un réseau', 'ein Netz(werk)', arts, genders) == 'phonetic'
    assert ec.classify_answer('un resaue', 'un réseau', 'ein Netz(werk)', arts, genders) == 'phonetic'


def test_classify_phonetic_harcelement():
    arts, genders = _articles_genders()
    assert ec.classify_answer('cyberarelement', 'cyberharcèlement', 'das Cyber-Mobbing', arts, genders) == 'phonetic'


def test_classify_genus_swap():
    arts, genders = _articles_genders()
    # right noun, wrong article
    assert ec.classify_answer('un nouvelle', 'une nouvelle', 'eine Nachricht', arts, genders) == 'genus'
    assert ec.classify_answer('une smartphone', 'un smartphone', 'ein Smartphone', arts, genders) == 'genus'


def test_classify_preposition_added():
    arts, genders = _articles_genders()
    # "contacter à qn" for "contacter qn" — spurious preposition
    assert ec.classify_answer('contacter a qn', 'contacter qn', 'in Verbindung treten', arts, genders) == 'preposition'


def test_classify_false_friend_missing_e():
    arts, genders = _articles_genders()
    # "un journalist" for "un journaliste" — German spelling, dropped -e
    assert ec.classify_answer('un journalist', 'un journaliste', 'ein Journalist', arts, genders) == 'false_friend'


def test_classify_false_friend_german_word():
    arts, genders = _articles_genders()
    # "un thema" for "un sujet" — German 'Thema' bled through
    assert ec.classify_answer('un thema', 'un sujet', 'ein Thema', arts, genders) == 'false_friend'


def test_noise_returns_none():
    arts, genders = _articles_genders()
    assert ec.classify_answer('d', 'un réseau', 'ein Netz', arts, genders) is None


# ---- cluster building -----------------------------------------------------

def test_build_clusters_groups_by_type():
    weak = [
        {'source': 'ein Netz(werk)', 'target': 'un réseau',
         'recentErrors': ['un resaue', 'un']},                       # phonetic (+noise)
        {'source': 'ein soziales Netzwerk', 'target': 'un réseau social',
         'recentErrors': ['un resau social', 'un resau Social']},    # phonetic
        {'source': 'eine Nachricht', 'target': 'une nouvelle',
         'recentErrors': ['un nouvelle']},                            # genus
        {'source': 'ein Journalist', 'target': 'un journaliste',
         'recentErrors': ['un journalist', 'un journlist']},          # false_friend
        {'source': 'in Verbindung treten', 'target': 'contacter qn',
         'recentErrors': ['contacter a qn']},                         # preposition
    ]
    clusters = ec.build_error_clusters(weak, 'fr')
    types = {c['type'] for c in clusters}
    assert {'phonetic', 'genus', 'false_friend', 'preposition'} <= types

    phon = next(c for c in clusters if c['type'] == 'phonetic')
    # both réseau words landed in the phonetic cluster -> one tip fixes two words
    assert phon['wordCount'] == 2

    # ordering: genus first (per _CLUSTER_ORDER), spelling last
    order = [c['type'] for c in clusters]
    assert order.index('genus') < order.index('phonetic')


def test_build_clusters_ignores_pure_noise_word():
    weak = [{'source': 'nur', 'target': 'ne que', 'recentErrors': ['ce ne', '?', 'f']}]
    clusters = ec.build_error_clusters(weak, 'fr')
    # 'ce ne' may or may not classify, but pure-noise answers must never crash
    assert isinstance(clusters, list)


def test_fallback_tips_shape():
    weak = [
        {'source': 'ein Netz', 'target': 'un réseau', 'recentErrors': ['un resau']},
        {'source': 'eine Nachricht', 'target': 'une nouvelle', 'recentErrors': ['un nouvelle']},
    ]
    clusters = ec.build_error_clusters(weak, 'fr')
    tips = ec.fallback_tips(clusters, limit=3)
    assert 1 <= len(tips) <= 3
    for t in tips:
        assert t['title'] and t['body'] and t['cluster']


def test_empty_input():
    assert ec.build_error_clusters([], 'fr') == []
    assert ec.build_error_clusters(None, 'fr') == []
    assert ec.fallback_tips([]) == []
