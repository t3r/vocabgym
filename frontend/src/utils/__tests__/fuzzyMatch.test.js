import { describe, it, expect } from 'vitest'
import { checkAnswer, normalizeAnswer, levenshteinDistance } from '@/utils/fuzzyMatch'

describe('normalizeAnswer', () => {
  it('lowercases text', () => {
    expect(normalizeAnswer('La Maison')).toBe('la maison')
  })

  it('trims whitespace', () => {
    expect(normalizeAnswer('  la maison  ')).toBe('la maison')
  })

  it('strips diacritical marks', () => {
    expect(normalizeAnswer('café')).toBe('cafe')
    expect(normalizeAnswer('naïve')).toBe('naive')
    expect(normalizeAnswer('élève')).toBe('eleve')
    expect(normalizeAnswer('garçon')).toBe('garcon')
  })

  it('removes square bracket content', () => {
    expect(normalizeAnswer('un mot [phonetic]')).toBe('un mot')
  })

  it('removes parenthesized content', () => {
    expect(normalizeAnswer('ein Wort (Anmerkung)')).toBe('ein wort')
  })

  it('removes punctuation', () => {
    expect(normalizeAnswer('la maison.')).toBe('la maison')
    expect(normalizeAnswer("l'école")).toBe('lecole')
    expect(normalizeAnswer('bonjour!')).toBe('bonjour')
  })

  it('normalizes multiple whitespace to single space', () => {
    expect(normalizeAnswer('la   maison')).toBe('la maison')
  })

  it('returns empty string for null/undefined', () => {
    expect(normalizeAnswer(null)).toBe('')
    expect(normalizeAnswer(undefined)).toBe('')
    expect(normalizeAnswer('')).toBe('')
  })
})

describe('levenshteinDistance', () => {
  it('returns 0 for identical strings', () => {
    expect(levenshteinDistance('hello', 'hello')).toBe(0)
  })

  it('returns length of other string when one is empty', () => {
    expect(levenshteinDistance('', 'abc')).toBe(3)
    expect(levenshteinDistance('abc', '')).toBe(3)
  })

  it('returns 1 for single character difference', () => {
    expect(levenshteinDistance('cat', 'bat')).toBe(1)
  })

  it('returns correct distance for insertions', () => {
    expect(levenshteinDistance('maison', 'maisonn')).toBe(1)
  })

  it('returns correct distance for deletions', () => {
    expect(levenshteinDistance('maison', 'maiso')).toBe(1)
  })

  it('handles completely different strings', () => {
    expect(levenshteinDistance('abc', 'xyz')).toBe(3)
  })
})

describe('checkAnswer', () => {
  it('returns exact for identical answers', () => {
    expect(checkAnswer('la maison', 'la maison')).toBe('exact')
  })

  it('returns exact for case-insensitive match', () => {
    expect(checkAnswer('La Maison', 'la maison')).toBe('exact')
  })

  it('returns exact for accent-insensitive match', () => {
    expect(checkAnswer('cafe', 'café')).toBe('exact')
  })

  it('returns close for single character typo', () => {
    expect(checkAnswer('la maisom', 'la maison')).toBe('close')
  })

  it('returns wrong for completely different answers', () => {
    expect(checkAnswer('le chat', 'la maison')).toBe('wrong')
  })

  it('returns wrong for empty input', () => {
    expect(checkAnswer('', 'la maison')).toBe('wrong')
  })

  it('returns wrong for null input', () => {
    expect(checkAnswer(null, 'la maison')).toBe('wrong')
  })

  it('returns wrong for null correct answer', () => {
    expect(checkAnswer('test', null)).toBe('wrong')
  })

  it('returns exact with leading/trailing whitespace', () => {
    expect(checkAnswer('  la maison  ', 'la maison')).toBe('exact')
  })

  it('returns exact when punctuation differs', () => {
    expect(checkAnswer('la maison.', 'la maison')).toBe('exact')
  })

  it('returns exact when bracket content stripped from correct answer', () => {
    expect(checkAnswer('un mot', 'un mot [phonetic]')).toBe('exact')
  })

  it('returns exact when parenthesized content stripped', () => {
    expect(checkAnswer('ein Wort', 'ein Wort (Anmerkung)')).toBe('exact')
  })

  it('handles multiple correct options separated by semicolon', () => {
    expect(checkAnswer('la maison', 'la maison; le logement')).toBe('exact')
    expect(checkAnswer('le logement', 'la maison; le logement')).toBe('exact')
  })

  it('handles multiple correct options separated by slash', () => {
    expect(checkAnswer('la maison', 'la maison / le logement')).toBe('exact')
  })

  it('returns close for near-match in multi-option answer', () => {
    expect(checkAnswer('la maisom', 'la maison; le logement')).toBe('close')
  })

  it('returns wrong when no option matches at all', () => {
    expect(checkAnswer('le chat', 'la maison; le logement')).toBe('wrong')
  })
})

describe('checkAnswer strict (exam) mode', () => {
  it('accepts an exact match with correct accents', () => {
    expect(checkAnswer('café', 'café', { strict: true })).toBe('exact')
  })

  it('rejects a missing accent (café vs cafe)', () => {
    expect(checkAnswer('cafe', 'café', { strict: true })).toBe('wrong')
  })

  it('rejects a wrong accent (éleve vs élève)', () => {
    expect(checkAnswer('éleve', 'élève', { strict: true })).toBe('wrong')
  })

  it('still ignores case', () => {
    expect(checkAnswer('Café', 'café', { strict: true })).toBe('exact')
  })

  it('still ignores surrounding punctuation', () => {
    expect(checkAnswer('café!', 'café', { strict: true })).toBe('exact')
    expect(checkAnswer('la maison.', 'la maison', { strict: true })).toBe('exact')
  })

  it('never returns close — a typo is simply wrong', () => {
    expect(checkAnswer('la maisom', 'la maison', { strict: true })).toBe('wrong')
  })

  it('accepts one matching option of a slash-separated answer', () => {
    expect(checkAnswer('l\'été', "l'été / la saison chaude", { strict: true })).toBe('exact')
  })

  it('rejects a slash option with a missing accent in strict mode', () => {
    expect(checkAnswer('ete', "l'été / la saison chaude", { strict: true })).toBe('wrong')
  })
})
