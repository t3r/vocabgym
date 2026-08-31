/**
 * Language registry for VocabGym.
 *
 * Every language is described the same way in a single `LANGUAGES` registry,
 * plus a curated `SUPPORTED_PAIRS` matrix of allowed source -> target
 * combinations.
 *
 * Historically German was always the source and only target languages were
 * configurable. That is now just the default: German (`de`) is a normal
 * registry entry and the curated pairs are all `de -> {fr,en,es,it}`, so
 * behaviour is unchanged. The generic structure lets us add other source
 * languages later (post-paid) without touching call sites.
 *
 * Backward compatibility: `SUPPORTED_LANGUAGES` (the 4 target languages),
 * `SOURCE_LANGUAGE`, `DEFAULT_TARGET_LANGUAGE`, `getLanguage`, `getLanguageName`,
 * `getLanguageFlag` and `getAllArticleGenders` are all preserved (derived from
 * the registry) and behave exactly as before.
 */

/**
 * Full registry: every language (including the source language German).
 * - register: address forms for this language's UI (post-paid i18n metadata).
 * - stripsDiacritics: whether answer checking may strip accents for this lang.
 * - latinScript: all currently supported languages are latin-script.
 */
export const LANGUAGES = {
  de: {
    code: 'de',
    name: 'Deutsch',
    endonym: 'Deutsch',
    flag: '🇩🇪',
    latinScript: true,
    stripsDiacritics: true,
    register: { informal: 'du', formal: 'Sie' },
    articles: {
      definite: ['der', 'die', 'das'],
      indefinite: ['ein', 'eine', 'eines', 'einem', 'einen', 'einer'],
    },
    articleGenders: {
      der: 'männlich (Maskulinum)',
      die: 'weiblich (Femininum) / Plural',
      das: 'sächlich (Neutrum)',
      ein: 'männlich / sächlich',
      eine: 'weiblich',
    },
  },
  fr: {
    code: 'fr',
    name: 'Französisch',
    endonym: 'Français',
    flag: '🇫🇷',
    latinScript: true,
    stripsDiacritics: true,
    register: { informal: 'tu', formal: 'vous' },
    articles: {
      definite: ['le', 'la', 'les', "l'"],
      indefinite: ['un', 'une', 'des', 'du', 'de la', "de l'"],
    },
    articleGenders: {
      le: 'männlich (Maskulinum)',
      la: 'weiblich (Femininum)',
      les: 'Plural',
      "l'": 'männlich oder weiblich (vor Vokal)',
      un: 'männlich (Maskulinum)',
      une: 'weiblich (Femininum)',
    },
  },
  en: {
    code: 'en',
    name: 'Englisch',
    endonym: 'English',
    flag: '🇬🇧',
    latinScript: true,
    stripsDiacritics: true,
    register: { neutral: 'you' },
    articles: {
      definite: ['the'],
      indefinite: ['a', 'an'],
    },
    articleGenders: {
      the: 'bestimmter Artikel',
      a: 'unbestimmter Artikel (vor Konsonant)',
      an: 'unbestimmter Artikel (vor Vokal)',
    },
  },
  es: {
    code: 'es',
    name: 'Spanisch',
    endonym: 'Español',
    flag: '🇪🇸',
    latinScript: true,
    stripsDiacritics: true,
    register: { informal: 'tú', formal: 'usted' },
    articles: {
      definite: ['el', 'la', 'los', 'las'],
      indefinite: ['un', 'una', 'unos', 'unas'],
    },
    articleGenders: {
      el: 'männlich (Maskulinum)',
      la: 'weiblich (Femininum)',
      los: 'männlich Plural',
      las: 'weiblich Plural',
      un: 'männlich (Maskulinum)',
      una: 'weiblich (Femininum)',
      unos: 'männlich Plural',
      unas: 'weiblich Plural',
    },
  },
  it: {
    code: 'it',
    name: 'Italienisch',
    endonym: 'Italiano',
    flag: '🇮🇹',
    latinScript: true,
    stripsDiacritics: true,
    register: { informal: 'tu', formal: 'Lei' },
    articles: {
      definite: ['il', 'lo', 'la', 'i', 'gli', 'le', "l'"],
      indefinite: ['un', 'uno', 'una', "un'"],
    },
    articleGenders: {
      il: 'männlich (Maskulinum)',
      lo: 'männlich (vor s+Konsonant, z)',
      la: 'weiblich (Femininum)',
      "l'": 'männlich oder weiblich (vor Vokal)',
      i: 'männlich Plural',
      gli: 'männlich Plural (vor Vokal, s+Kons., z)',
      le: 'weiblich Plural',
      un: 'männlich (Maskulinum)',
      uno: 'männlich (vor s+Konsonant, z)',
      una: 'weiblich (Femininum)',
      "un'": 'weiblich (vor Vokal)',
    },
  },
}

/**
 * Curated source -> target pairs. For now only German-source pairs, so nothing
 * changes for existing behaviour.
 */
export const SUPPORTED_PAIRS = [
  { source: 'de', target: 'fr', promptKey: 'de-fr' },
  { source: 'de', target: 'en', promptKey: 'de-en' },
  { source: 'de', target: 'es', promptKey: 'de-es' },
  { source: 'de', target: 'it', promptKey: 'de-it' },
]

export const DEFAULT_SOURCE_LANGUAGE = 'de'

/**
 * Default target language code.
 */
export const DEFAULT_TARGET_LANGUAGE = 'fr'

/**
 * Source language (German) configuration — derived from the registry.
 * Preserved for backward compatibility.
 */
export const SOURCE_LANGUAGE = {
  code: LANGUAGES.de.code,
  name: LANGUAGES.de.name,
  flag: LANGUAGES.de.flag,
  articles: LANGUAGES.de.articles,
  articleGenders: LANGUAGES.de.articleGenders,
}

/**
 * Supported target languages (fr, en, es, it) — derived from the pair matrix
 * for the default German source. Preserved for backward compatibility: this
 * intentionally does NOT include the source language.
 */
export const SUPPORTED_LANGUAGES = Object.fromEntries(
  SUPPORTED_PAIRS
    .filter((p) => p.source === DEFAULT_SOURCE_LANGUAGE)
    .map((p) => [p.target, LANGUAGES[p.target]])
)

// ---------------------------------------------------------------------------
// New generic helpers
// ---------------------------------------------------------------------------

/**
 * Return the full registry entry for a language code (incl. the source lang).
 * @param {string} code
 * @returns {object|undefined}
 */
export function getRegistryLanguage(code) {
  return LANGUAGES[code]
}

/**
 * Return the curated pair for source->target, or undefined if unsupported.
 * @param {string} source
 * @param {string} target
 * @returns {object|undefined}
 */
export function getPair(source, target) {
  return SUPPORTED_PAIRS.find((p) => p.source === source && p.target === target)
}

/**
 * True if the source->target combination is a curated, supported pair.
 * @param {string} source
 * @param {string} target
 * @returns {boolean}
 */
export function isPairSupported(source, target) {
  return getPair(source, target) !== undefined
}

// ---------------------------------------------------------------------------
// Backward-compatible helpers (unchanged behaviour)
// ---------------------------------------------------------------------------

/**
 * Get target-language configuration by code.
 * @param {string} code - Language code (e.g. 'fr', 'en', 'es', 'it')
 * @returns {object|undefined} Language configuration object
 */
export function getLanguage(code) {
  return SUPPORTED_LANGUAGES[code]
}

/**
 * Get the German UI name for a language code. Resolves against the full
 * registry so source-language codes (e.g. 'de') also resolve.
 * @param {string} code - Language code
 * @returns {string} German name of the language, or the code itself if unknown
 */
export function getLanguageName(code) {
  return LANGUAGES[code]?.name || code
}

/**
 * Get the flag emoji for a language code (resolves against the full registry).
 * @param {string} code - Language code
 * @returns {string} Flag emoji, or empty string if unknown
 */
export function getLanguageFlag(code) {
  return LANGUAGES[code]?.flag || ''
}

/**
 * Get all article-to-gender mappings for both source (German) and target language.
 * @param {string} targetCode - Target language code
 * @returns {object} Merged object of article -> German gender explanation
 */
export function getAllArticleGenders(targetCode) {
  const targetLang = SUPPORTED_LANGUAGES[targetCode]
  const targetGenders = targetLang?.articleGenders || {}
  return { ...SOURCE_LANGUAGE.articleGenders, ...targetGenders }
}
