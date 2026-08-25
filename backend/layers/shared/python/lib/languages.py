"""
Supported target languages for VocabGym vocabulary training.

Source language is always German. Target languages can be French, English,
Spanish, or Italian.
"""

SOURCE_LANGUAGE = {
    "code": "de",
    "name": "Deutsch",
    "nameEnglish": "German",
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
}

SUPPORTED_LANGUAGES = {
    "fr": {
        "code": "fr",
        "name": "Französisch",
        "nameEnglish": "French",
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
        "ocrPromptHint": (
            "Extract German-French vocabulary pairs from this image. "
            "The left column contains German words/phrases and the right column "
            "contains their French translations."
        ),
        "examplePair": {
            "source": "das Haus",
            "target": "la maison",
        },
    },
    "en": {
        "code": "en",
        "name": "Englisch",
        "nameEnglish": "English",
        "articles": {
            "definite": ["the"],
            "indefinite": ["a", "an"],
        },
        "articleGenders": {
            "a": "unbestimmt (Singular)",
            "an": "unbestimmt (vor Vokal)",
            "the": "bestimmt",
        },
        "ocrPromptHint": (
            "Extract German-English vocabulary pairs from this image. "
            "The left column contains German words/phrases and the right column "
            "contains their English translations."
        ),
        "examplePair": {
            "source": "das Haus",
            "target": "the house",
        },
    },
    "es": {
        "code": "es",
        "name": "Spanisch",
        "nameEnglish": "Spanish",
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
        "ocrPromptHint": (
            "Extract German-Spanish vocabulary pairs from this image. "
            "The left column contains German words/phrases and the right column "
            "contains their Spanish translations."
        ),
        "examplePair": {
            "source": "das Haus",
            "target": "la casa",
        },
    },
    "it": {
        "code": "it",
        "name": "Italienisch",
        "nameEnglish": "Italian",
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
        "ocrPromptHint": (
            "Extract German-Italian vocabulary pairs from this image. "
            "The left column contains German words/phrases and the right column "
            "contains their Italian translations."
        ),
        "examplePair": {
            "source": "das Haus",
            "target": "la casa",
        },
    },
}

DEFAULT_TARGET_LANGUAGE = "fr"


def get_language(code):
    """Return the language definition for a given language code, or None."""
    return SUPPORTED_LANGUAGES.get(code)


def get_all_articles(target_language_code):
    """
    Merge source (German) and target language article lists into a single flat list.

    Returns all definite and indefinite articles from both languages combined.
    Returns None if target_language_code is not supported.
    """
    target = SUPPORTED_LANGUAGES.get(target_language_code)
    if target is None:
        return None

    articles = []
    # Source language articles
    articles.extend(SOURCE_LANGUAGE["articles"]["definite"])
    articles.extend(SOURCE_LANGUAGE["articles"]["indefinite"])
    # Target language articles
    articles.extend(target["articles"]["definite"])
    articles.extend(target["articles"]["indefinite"])
    return articles


def get_article_genders(target_language_code):
    """
    Merge source (German) and target language articleGenders dicts.

    Returns a combined dict mapping article strings to their German gender
    explanations. Returns None if target_language_code is not supported.
    """
    target = SUPPORTED_LANGUAGES.get(target_language_code)
    if target is None:
        return None

    merged = {}
    merged.update(SOURCE_LANGUAGE["articleGenders"])
    merged.update(target["articleGenders"])
    return merged
