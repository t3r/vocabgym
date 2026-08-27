import { describe, it, expect } from 'vitest'
import {
  SUPPORTED_LANGUAGES,
  SOURCE_LANGUAGE,
  DEFAULT_TARGET_LANGUAGE,
  getLanguage,
  getLanguageName,
  getLanguageFlag,
  getAllArticleGenders,
} from '@/utils/languages'

describe('SUPPORTED_LANGUAGES', () => {
  it('has exactly 4 entries', () => {
    expect(Object.keys(SUPPORTED_LANGUAGES)).toHaveLength(4)
  })

  it('contains fr, en, es, it', () => {
    expect(Object.keys(SUPPORTED_LANGUAGES).sort()).toEqual(['en', 'es', 'fr', 'it'])
  })

  it('each language has required fields', () => {
    for (const [code, lang] of Object.entries(SUPPORTED_LANGUAGES)) {
      expect(lang.code).toBe(code)
      expect(lang.name).toBeTruthy()
      expect(lang.flag).toBeTruthy()
      expect(lang.articles).toBeDefined()
      expect(lang.articleGenders).toBeDefined()
    }
  })
})

describe('SOURCE_LANGUAGE', () => {
  it('is German', () => {
    expect(SOURCE_LANGUAGE.code).toBe('de')
    expect(SOURCE_LANGUAGE.name).toBe('Deutsch')
    expect(SOURCE_LANGUAGE.flag).toBe('🇩🇪')
  })

  it('has articles and gender mappings', () => {
    expect(SOURCE_LANGUAGE.articles.definite).toContain('der')
    expect(SOURCE_LANGUAGE.articles.definite).toContain('die')
    expect(SOURCE_LANGUAGE.articles.definite).toContain('das')
    expect(SOURCE_LANGUAGE.articleGenders.der).toBeDefined()
  })
})

describe('DEFAULT_TARGET_LANGUAGE', () => {
  it('is French', () => {
    expect(DEFAULT_TARGET_LANGUAGE).toBe('fr')
  })
})

describe('getLanguage', () => {
  it('returns French config for "fr"', () => {
    const lang = getLanguage('fr')
    expect(lang.code).toBe('fr')
    expect(lang.name).toBe('Französisch')
  })

  it('returns undefined for unknown code', () => {
    expect(getLanguage('xx')).toBeUndefined()
  })
})

describe('getLanguageName', () => {
  it('returns Französisch for "fr"', () => {
    expect(getLanguageName('fr')).toBe('Französisch')
  })

  it('returns Englisch for "en"', () => {
    expect(getLanguageName('en')).toBe('Englisch')
  })

  it('returns Spanisch for "es"', () => {
    expect(getLanguageName('es')).toBe('Spanisch')
  })

  it('returns Italienisch for "it"', () => {
    expect(getLanguageName('it')).toBe('Italienisch')
  })

  it('returns the code itself for unknown language', () => {
    expect(getLanguageName('xx')).toBe('xx')
  })
})

describe('getLanguageFlag', () => {
  it('returns 🇫🇷 for "fr"', () => {
    expect(getLanguageFlag('fr')).toBe('🇫🇷')
  })

  it('returns 🇬🇧 for "en"', () => {
    expect(getLanguageFlag('en')).toBe('🇬🇧')
  })

  it('returns 🇪🇸 for "es"', () => {
    expect(getLanguageFlag('es')).toBe('🇪🇸')
  })

  it('returns 🇮🇹 for "it"', () => {
    expect(getLanguageFlag('it')).toBe('🇮🇹')
  })

  it('returns empty string for unknown language', () => {
    expect(getLanguageFlag('xx')).toBe('')
  })
})

describe('getAllArticleGenders', () => {
  it('merges German and French article genders', () => {
    const genders = getAllArticleGenders('fr')
    // German articles
    expect(genders.der).toBeDefined()
    expect(genders.die).toBeDefined()
    expect(genders.das).toBeDefined()
    // French articles
    expect(genders.le).toBeDefined()
    expect(genders.la).toBeDefined()
  })

  it('merges German and Spanish article genders', () => {
    const genders = getAllArticleGenders('es')
    expect(genders.der).toBeDefined()
    expect(genders.el).toBeDefined()
  })

  it('returns only German genders for unknown target', () => {
    const genders = getAllArticleGenders('xx')
    expect(genders.der).toBeDefined()
    expect(Object.keys(genders)).toHaveLength(Object.keys(SOURCE_LANGUAGE.articleGenders).length)
  })
})
