/**
 * Language configuration for VocabGym.
 *
 * Defines supported target languages, source language (German),
 * articles, and gender explanations for vocabulary practice.
 */

/**
 * Supported target languages for vocabulary practice.
 * Each language includes articles and gender explanations used
 * in the review and practice interfaces.
 */
export const SUPPORTED_LANGUAGES = {
  fr: {
    code: 'fr',
    name: 'Französisch',
    flag: '🇫🇷',
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
    flag: '🇬🇧',
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
    flag: '🇪🇸',
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
    flag: '🇮🇹',
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
 * Source language (German) configuration.
 */
export const SOURCE_LANGUAGE = {
  code: 'de',
  name: 'Deutsch',
  flag: '🇩🇪',
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
}

/**
 * Default target language code.
 */
export const DEFAULT_TARGET_LANGUAGE = 'fr'

/**
 * Get language configuration by code.
 * @param {string} code - Language code (e.g. 'fr', 'en', 'es', 'it')
 * @returns {object|undefined} Language configuration object
 */
export function getLanguage(code) {
  return SUPPORTED_LANGUAGES[code]
}

/**
 * Get the German UI name for a language code.
 * @param {string} code - Language code
 * @returns {string} German name of the language, or the code itself if unknown
 */
export function getLanguageName(code) {
  return SUPPORTED_LANGUAGES[code]?.name || code
}

/**
 * Get the flag emoji for a language code.
 * @param {string} code - Language code
 * @returns {string} Flag emoji, or empty string if unknown
 */
export function getLanguageFlag(code) {
  return SUPPORTED_LANGUAGES[code]?.flag || ''
}

/**
 * Get all article-to-gender mappings for both source (German) and target language.
 * Useful for displaying gender hints in the review and practice views.
 * @param {string} targetCode - Target language code
 * @returns {object} Merged object of article -> German gender explanation
 */
export function getAllArticleGenders(targetCode) {
  const targetLang = SUPPORTED_LANGUAGES[targetCode]
  const targetGenders = targetLang?.articleGenders || {}
  return { ...SOURCE_LANGUAGE.articleGenders, ...targetGenders }
}
