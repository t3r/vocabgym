"""
Language registry for VocabGym vocabulary training.

This module describes every supported language generically in a single
``LANGUAGES`` registry, plus a curated ``SUPPORTED_PAIRS`` matrix of allowed
source -> target combinations.

Historically the source language was always German and only target languages
were configurable. That is now just the *default*: German (``de``) is a normal
registry entry and the current curated pairs are all ``de -> {fr,en,es,it}``,
so behaviour is unchanged. The generic structure lets us add other source
languages later (post-paid) without touching call sites.

Backward compatibility: ``SOURCE_LANGUAGE``, ``SUPPORTED_LANGUAGES``,
``DEFAULT_TARGET_LANGUAGE``, ``get_language``, ``get_all_articles`` and
``get_article_genders`` are all preserved (derived from the registry) and behave
exactly as before.
"""

# ---------------------------------------------------------------------------
# Registry: every language described the same way.
#   register: address forms available in this language's UI (post-paid i18n).
#             'de' has informal/formal (du/Sie); romance langs tu/vous, tú/usted;
#             'en' is neutral. Only metadata for now — not yet consumed.
#   stripsDiacritics: whether answer checking may strip accents for this language
#             (true for latin-script langs here; kept explicit for future langs).
#   pollyVoices: candidate Amazon Polly voice ids (first = default).
#   latinScript: all currently supported languages are latin-script.
# ---------------------------------------------------------------------------

LANGUAGES = {
    "de": {
        "code": "de",
        "name": "Deutsch",          # German UI display name
        "nameEnglish": "German",
        "endonym": "Deutsch",
        "flag": "🇩🇪",
        "latinScript": True,
        "stripsDiacritics": True,
        "register": {"informal": "du", "formal": "Sie"},
        "pollyVoices": ["Vicki", "Daniel", "Hans", "Marlene"],
        "articles": {
            "definite": ["der", "die", "das"],
            "indefinite": ["ein", "eine", "eines", "einem", "einen", "einer"],
        },
        "articleGenders": {
            "der": "männlich (Maskulinum)",
            "die": "weiblich (Femininum) / Plural",
            "das": "sächlich (Neutrum)",
            "ein": "männlich/sächlich",
            "eine": "weiblich",
        },
    },
    "fr": {
        "code": "fr",
        "name": "Französisch",
        "nameEnglish": "French",
        "endonym": "Français",
        "flag": "🇫🇷",
        "latinScript": True,
        "stripsDiacritics": True,
        "register": {"informal": "tu", "formal": "vous"},
        "pollyVoices": ["Lea", "Celine", "Mathieu"],
        "articles": {
            "definite": ["le", "la", "les", "l'"],
            "indefinite": ["un", "une", "des", "du", "de la", "de l'", "de les"],
        },
        "articleGenders": {
            "un": "männlich (masculin)",
            "une": "weiblich (féminin)",
            "le": "männlich (masculin)",
            "la": "weiblich (féminin)",
            "les": "Plural",
            "des": "Plural (unbestimmt)",
            "l'": "männlich oder weiblich (vor Vokal)",
        },
        "examplePair": {"source": "das Haus", "target": "la maison"},
    },
    "en": {
        "code": "en",
        "name": "Englisch",
        "nameEnglish": "English",
        "endonym": "English",
        "flag": "🇬🇧",
        "latinScript": True,
        "stripsDiacritics": True,
        "register": {"neutral": "you"},
        "pollyVoices": ["Joanna", "Matthew", "Amy", "Brian"],
        "articles": {
            "definite": ["the"],
            "indefinite": ["a", "an"],
        },
        "articleGenders": {
            "a": "unbestimmt (Singular)",
            "an": "unbestimmt (vor Vokal)",
            "the": "bestimmt",
        },
        "examplePair": {"source": "das Haus", "target": "the house"},
    },
    "es": {
        "code": "es",
        "name": "Spanisch",
        "nameEnglish": "Spanish",
        "endonym": "Español",
        "flag": "🇪🇸",
        "latinScript": True,
        "stripsDiacritics": True,
        "register": {"informal": "tú", "formal": "usted"},
        "pollyVoices": ["Lucia", "Conchita", "Enrique"],
        "articles": {
            "definite": ["el", "la", "los", "las"],
            "indefinite": ["un", "una", "unos", "unas"],
        },
        "articleGenders": {
            "el": "männlich (masculino)",
            "la": "weiblich (femenino)",
            "los": "männlich Plural",
            "las": "weiblich Plural",
            "un": "männlich (unbestimmt)",
            "una": "weiblich (unbestimmt)",
        },
        "examplePair": {"source": "das Haus", "target": "la casa"},
    },
    "it": {
        "code": "it",
        "name": "Italienisch",
        "nameEnglish": "Italian",
        "endonym": "Italiano",
        "flag": "🇮🇹",
        "latinScript": True,
        "stripsDiacritics": True,
        "register": {"informal": "tu", "formal": "Lei"},
        "pollyVoices": ["Bianca", "Carla", "Giorgio"],
        "articles": {
            "definite": ["il", "lo", "la", "i", "gli", "le", "l'"],
            "indefinite": ["un", "uno", "una", "un'"],
        },
        "articleGenders": {
            "il": "männlich (maschile)",
            "lo": "männlich (vor s+Kons., z)",
            "la": "weiblich (femminile)",
            "le": "weiblich Plural",
            "un": "männlich (unbestimmt)",
            "una": "weiblich (unbestimmt)",
        },
        "examplePair": {"source": "das Haus", "target": "la casa"},
    },
}


# ---------------------------------------------------------------------------
# Curated source -> target pairs. For now only German-source pairs, so nothing
# changes for existing behaviour. promptKey selects the extraction prompt
# (post-paid: per-pair SSM prompt; today all German-source pairs share the
# existing prompt keyed 'de-*').
# ---------------------------------------------------------------------------

SUPPORTED_PAIRS = [
    {"source": "de", "target": "fr", "promptKey": "de-fr"},
    {"source": "de", "target": "en", "promptKey": "de-en"},
    {"source": "de", "target": "es", "promptKey": "de-es"},
    {"source": "de", "target": "it", "promptKey": "de-it"},
]

DEFAULT_SOURCE_LANGUAGE = "de"
DEFAULT_TARGET_LANGUAGE = "fr"


# ---------------------------------------------------------------------------
# New generic helpers
# ---------------------------------------------------------------------------

def get_registry_language(code):
    """Return the full registry entry for a language code, or None."""
    return LANGUAGES.get(code)


def get_pair(source_code, target_code):
    """Return the curated pair dict for source->target, or None if unsupported."""
    for pair in SUPPORTED_PAIRS:
        if pair["source"] == source_code and pair["target"] == target_code:
            return pair
    return None


def is_pair_supported(source_code, target_code):
    """True if the source->target combination is a curated, supported pair."""
    return get_pair(source_code, target_code) is not None


def get_articles(code):
    """Return the flat article list (definite + indefinite) for one language."""
    lang = LANGUAGES.get(code)
    if lang is None:
        return None
    return list(lang["articles"]["definite"]) + list(lang["articles"]["indefinite"])


# ---------------------------------------------------------------------------
# Backward-compatible symbols and helpers (derived from the registry).
# These preserve the historical "German source, configurable target" API.
# ---------------------------------------------------------------------------

# The historical source language (German).
SOURCE_LANGUAGE = {
    "code": LANGUAGES["de"]["code"],
    "name": LANGUAGES["de"]["name"],
    "nameEnglish": LANGUAGES["de"]["nameEnglish"],
    "articles": LANGUAGES["de"]["articles"],
    "articleGenders": LANGUAGES["de"]["articleGenders"],
}

# Historical target-language map: every language reachable as a target from the
# default German source. Currently fr, en, es, it — matching the old contents.
SUPPORTED_LANGUAGES = {
    code: LANGUAGES[code]
    for code in [
        p["target"] for p in SUPPORTED_PAIRS if p["source"] == DEFAULT_SOURCE_LANGUAGE
    ]
}


def get_language(code):
    """Return the target-language definition for a code, or None.

    Preserved for backward compatibility — only resolves target languages
    (fr/en/es/it), exactly like before. Use get_registry_language() for the
    full registry incl. the source language.
    """
    return SUPPORTED_LANGUAGES.get(code)


def get_all_articles(target_language_code):
    """Merge source (German) and target language article lists into one flat list.

    Returns None if target_language_code is not supported. Behaviour preserved.
    """
    target = SUPPORTED_LANGUAGES.get(target_language_code)
    if target is None:
        return None

    articles = []
    articles.extend(SOURCE_LANGUAGE["articles"]["definite"])
    articles.extend(SOURCE_LANGUAGE["articles"]["indefinite"])
    articles.extend(target["articles"]["definite"])
    articles.extend(target["articles"]["indefinite"])
    return articles


def get_article_genders(target_language_code):
    """Merge source (German) and target language articleGenders dicts.

    Returns None if target_language_code is not supported. Behaviour preserved.
    """
    target = SUPPORTED_LANGUAGES.get(target_language_code)
    if target is None:
        return None

    merged = {}
    merged.update(SOURCE_LANGUAGE["articleGenders"])
    merged.update(target["articleGenders"])
    return merged
