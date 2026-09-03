"""Rule-based classification of a learner's mistakes into shared error clusters.

Pure, deterministic, dependency-light logic (no AWS, no LLM). Given the weak
words (mastery < 4) with their recorded wrong answers, it groups the mistakes by
*type* so that one tip can fix several words at once:

  - genus        : right word, wrong article (le/la/un/une …)
  - preposition  : verb construction with a wrong/missing preposition (à, avec …)
  - false_friend : German spelling / interference bled into the French word
  - phonetic     : written the way it sounds (réseau -> "resau", -eau/-eaux, …)
  - spelling     : close miss not covered by the above (fallback)

Noise (empty, single-character, punctuation-only, or abandoned inputs like
"d" / "?" / ".") is filtered out first so we never build advice on non-errors.

The LLM only *phrases* tips from these clusters; the analysis lives here so it
stays correct, cheap and fully testable.
"""

import re
import unicodedata

# French prepositions that commonly attach to verbs (used to spot à/avec/de
# add/drop/swap errors like "contacter à qn" for "contacter qn").
_FR_PREPOSITIONS = {'à', 'a', 'au', 'aux', 'avec', 'de', 'des', 'du', 'en', 'sur', 'pour'}

# A short, curated fallback tip per cluster type (used when the LLM is
# unavailable). Kept factual and in Du-Form (student UI).
_FALLBACK_TIPS = {
    'genus': {
        'title': 'Achte auf den Artikel (Genus)',
        'body': 'Bei diesen Wörtern stimmt das Wort, aber der Artikel ist falsch. '
                'Lerne das Wort immer MIT Artikel (z. B. „une souris“, „un sujet“) — '
                'der Artikel gehört dazu wie eine Farbe zum Wort.',
    },
    'preposition': {
        'title': 'Die kleine Präposition entscheidet',
        'body': 'Hier fehlt oder stört eine Präposition (à, avec, de). Merke dir die '
                'Verben samt ihrer Präposition als festen Baustein, z. B. '
                '„jouer À un jeu“, „partager qc AVEC qn“, „contacter qn“ (ohne à).',
    },
    'false_friend': {
        'title': 'Vorsicht, falscher Freund',
        'body': 'Diese Wörter schreibst du wie im Deutschen. Präg dir die '
                'französische Form bewusst ein, z. B. „un sujet“ (nicht „thema“) '
                'und „un/une journaliste“ (mit -e).',
    },
    'phonetic': {
        'title': 'Schreibung ≠ Aussprache',
        'body': 'Du schreibst so, wie es klingt. Achte auf typische Endungen: '
                '„-eau/-eaux“ klingt wie „o“ (un réseau, des réseaux), und Accents/'
                'Doppelbuchstaben (harcèlement) gehören dazu.',
    },
    'spelling': {
        'title': 'Genau hinschauen bei der Schreibung',
        'body': 'Ein, zwei Buchstaben daneben — lies das Wort langsam Silbe für '
                'Silbe und schreib es ein paarmal ab, um die Form zu festigen.',
    },
}

# Very short, one-line rules per cluster type — shown inline in practice next to
# a hard word ("💡 Denk an: …"). Kept deterministic (no LLM) so the hint is
# instant, free and always correct.
_SHORT_RULES = {
    'genus': 'Lern das Wort mit Artikel — das Genus gehört dazu.',
    'preposition': 'Achte auf die Präposition (à / avec / de) beim Verb.',
    'false_friend': 'Kein Deutsch schreiben — merk dir die französische Form.',
    'phonetic': 'Nicht schreiben wie es klingt — achte auf Endungen & Accents.',
    'spelling': 'Genau buchstabieren — lies das Wort Silbe für Silbe.',
}

# Order in which clusters are presented (most impactful / most teachable first).
_CLUSTER_ORDER = ['genus', 'preposition', 'false_friend', 'phonetic', 'spelling']


def _strip_accents(text):
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def _norm(text):
    """Lowercase, strip accents/punctuation, collapse whitespace."""
    if not text:
        return ''
    t = _strip_accents(text.strip().lower())
    t = re.sub(r"[.,;:!?/'\"()\[\]{}\-]", ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def _tokens(text):
    return [t for t in _norm(text).split(' ') if t]


def is_noise(answer, target):
    """True if a recorded 'wrong answer' is not a real attempt.

    Abandoned/test inputs: empty, single character, punctuation-only, or a bare
    article/preposition with no content word.
    """
    if not answer:
        return True
    stripped = answer.strip()
    if len(stripped) <= 1:
        return True
    norm = _norm(answer)
    if not norm:
        return True
    toks = norm.split(' ')
    # Only an article/preposition, nothing else -> not a real attempt.
    if all(t in _FR_PREPOSITIONS or len(t) <= 1 for t in toks):
        return True
    return False


def _phonetic_key(text):
    """Collapse French orthography to a rough phonetic skeleton so that a
    sound-alike misspelling maps onto the target. Deliberately crude but enough
    to catch the observed pattern (réseau/reseau/resau, harcèlement/arcelement).
    """
    t = _norm(text)
    t = t.replace('eaux', 'o').replace('eau', 'o')
    t = t.replace('aux', 'o').replace('au', 'o')
    t = t.replace('ss', 's')
    t = re.sub(r'(.)\1+', r'\1', t)        # collapse doubled letters
    t = re.sub(r'[hx]', '', t)             # silent-ish h, trailing x
    t = re.sub(r's\b', '', t)              # silent plural s
    t = t.replace(' ', '')
    return t


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _first_option(target):
    """Targets may list options ('un journaliste / une journaliste'); use the
    first for classification but keep matching lenient."""
    for sep in ['/', ';']:
        if sep in target:
            return target.split(sep)[0].strip()
    return target.strip()


def classify_answer(answer, target, source, articles, article_genders):
    """Classify a single wrong answer against its target. Returns a cluster type
    string, or None if it's noise / unclassifiable.
    """
    if is_noise(answer, target):
        return None

    tgt = _first_option(target)
    a_norm = _norm(answer)
    t_norm = _norm(tgt)
    if not a_norm or not t_norm:
        return None

    a_toks = a_norm.split(' ')
    t_toks = t_norm.split(' ')

    # --- genus: both start with an article, the rest matches, article differs
    if len(a_toks) >= 2 and len(t_toks) >= 2:
        a_art, t_art = a_toks[0], t_toks[0]
        if a_art in articles and t_art in articles and a_art != t_art:
            if ' '.join(a_toks[1:]) == ' '.join(t_toks[1:]):
                # Only a genuine gender swap (both articles known genders).
                if (not article_genders
                        or (a_art in article_genders and t_art in article_genders)):
                    return 'genus'

    # --- preposition: same content words, but a preposition was added/dropped/swapped
    a_prep = [t for t in a_toks if t in _FR_PREPOSITIONS]
    t_prep = [t for t in t_toks if t in _FR_PREPOSITIONS]
    a_content = [t for t in a_toks if t not in _FR_PREPOSITIONS and t not in articles]
    t_content = [t for t in t_toks if t not in _FR_PREPOSITIONS and t not in articles]
    if a_content == t_content and a_prep != t_prep and (a_prep or t_prep):
        return 'preposition'

    # --- false friend / German interference: the answer equals (or is very
    # close to) the German source, OR its content word echoes the German word,
    # OR it drops a French-specific ending like -e.
    src_norm = _norm(source)
    if src_norm and (a_norm == src_norm or _levenshtein(a_norm, src_norm) <= 1):
        return 'false_friend'
    # Compare article-stripped content: "un thema" vs source "ein Thema" -> the
    # content word "thema" matches the German source content, not the French.
    src_content = [t for t in src_norm.split(' ') if t not in articles]
    if a_content and src_content:
        a_c = ' '.join(a_content)
        s_c = ' '.join(src_content)
        if a_c and (a_c == s_c or _levenshtein(a_c, s_c) <= 1) and a_c != ' '.join(t_content):
            return 'false_friend'
    # e.g. "journalist" for "journaliste": answer is target minus a trailing 'e'
    if t_norm.endswith('e') and a_norm == t_norm[:-1]:
        return 'false_friend'

    # --- phonetic: sounds right, spelled wrong (collapse FR orthography)
    ak, tk = _phonetic_key(answer), _phonetic_key(tgt)
    if ak and tk and (ak == tk or _levenshtein(ak, tk) <= 1):
        # Only call it phonetic if the raw forms actually differ in spelling.
        if a_norm != t_norm:
            return 'phonetic'

    # --- spelling fallback: reasonably close miss
    dist = _levenshtein(a_norm, t_norm)
    if 0 < dist <= max(2, len(t_norm) // 3):
        return 'spelling'

    return None


def build_error_clusters(weak_words, target_language='fr'):
    """Group weak words by dominant error type.

    Args:
        weak_words: list of dicts with keys source, target, recentErrors (list
            of strings), and optionally level/correct/incorrect.
        target_language: language code for article/gender lookup.

    Returns:
        list of clusters, each: {
            'type': str, 'title': str, 'fallbackTip': str,
            'words': [{'source','target','examples':[wrong,...]}],
            'wordCount': int,
        }
        ordered by _CLUSTER_ORDER then by word count desc. Empty if nothing
        classifiable.
    """
    from lib.languages import get_all_articles, get_article_genders

    articles = set(_norm(a) for a in (get_all_articles(target_language) or []))
    article_genders_raw = get_article_genders(target_language) or {}
    article_genders = set(_norm(a) for a in article_genders_raw.keys())

    clusters = {}  # type -> {word_key -> {'source','target','examples':set}}
    for w in weak_words or []:
        target = w.get('target') or w.get('french') or ''
        source = w.get('source') or w.get('german') or ''
        if not target:
            continue
        # Count classified errors per type for THIS word; assign it to its
        # dominant (most frequent) error type.
        type_counts = {}
        examples_by_type = {}
        for ans in (w.get('recentErrors') or []):
            ctype = classify_answer(ans, target, source, articles, article_genders)
            if not ctype:
                continue
            type_counts[ctype] = type_counts.get(ctype, 0) + 1
            examples_by_type.setdefault(ctype, []).append(ans.strip())
        if not type_counts:
            continue
        dominant = max(type_counts.items(), key=lambda kv: kv[1])[0]
        bucket = clusters.setdefault(dominant, {})
        key = f"{source}|{target}"
        entry = bucket.setdefault(key, {'source': source, 'target': target, 'examples': []})
        # keep up to 3 distinct example mistakes
        for ex in examples_by_type[dominant]:
            if ex and ex not in entry['examples'] and len(entry['examples']) < 3:
                entry['examples'].append(ex)

    result = []
    for ctype in _CLUSTER_ORDER:
        if ctype not in clusters:
            continue
        words = list(clusters[ctype].values())
        tip = _FALLBACK_TIPS[ctype]
        result.append({
            'type': ctype,
            'title': tip['title'],
            'fallbackTip': tip['body'],
            'words': words,
            'wordCount': len(words),
        })
    # Within the fixed type order, larger clusters are more worth addressing.
    result.sort(key=lambda c: (_CLUSTER_ORDER.index(c['type']), -c['wordCount']))
    return result


def fallback_tips(clusters, limit=3):
    """Produce ready-to-show tips from clusters WITHOUT an LLM (used as the
    graceful fallback). Returns [{'title','body','cluster'}]."""
    tips = []
    for c in clusters[:limit]:
        examples = []
        for w in c['words'][:3]:
            examples.append(w['target'])
        example_str = f" (z. B. {', '.join(examples)})" if examples else ''
        tips.append({
            'title': c['title'],
            'body': c['fallbackTip'] + example_str,
            'cluster': c['type'],
        })
    return tips



def rule_for_word(target, source, recent_errors, target_language='fr'):
    """Return a short, deterministic rule hint for a single word, or None.

    Used to surface an inline "💡 Denk an: …" hint in practice for a word the
    learner keeps getting wrong. The word is classified by the SAME rules as the
    learning-tips clusters (so the hint and the tips stay consistent), then
    mapped to a one-line rule from _SHORT_RULES.

    Args:
        target: the correct target-language word.
        source: the German source word.
        recent_errors: list of the learner's recorded wrong answers (strings).
        target_language: language code for article/gender lookup.

    Returns:
        {'cluster': <type>, 'rule': <short text>} for the dominant error type,
        or None when the word has no classifiable mistakes (e.g. only noise).
    """
    from lib.languages import get_all_articles, get_article_genders

    if not target or not recent_errors:
        return None

    articles = set(_norm(a) for a in (get_all_articles(target_language) or []))
    article_genders = set(_norm(a) for a in (get_article_genders(target_language) or {}).keys())

    counts = {}
    for ans in recent_errors:
        ctype = classify_answer(ans, target, source, articles, article_genders)
        if ctype:
            counts[ctype] = counts.get(ctype, 0) + 1
    if not counts:
        return None

    dominant = max(counts.items(), key=lambda kv: kv[1])[0]
    rule = _SHORT_RULES.get(dominant)
    if not rule:
        return None
    return {'cluster': dominant, 'rule': rule}
