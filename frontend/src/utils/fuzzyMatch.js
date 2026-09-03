/**
 * Fuzzy matching utilities for answer validation in practice sessions.
 * Handles accents, case differences, whitespace, and minor typos.
 */

/**
 * Normalize an answer string for comparison:
 * - Lowercase
 * - Trim whitespace
 * - Strip diacritical marks (é → e, ç → c, etc.)
 * - Remove common punctuation
 *
 * @param {string} text
 * @param {object} [options]
 * @param {boolean} [options.keepAccents=false] When true, diacritical marks are
 *   preserved (é stays é). Case, whitespace, brackets and punctuation are still
 *   normalized. Used by the strict exam comparison where accents must match.
 */
export function normalizeAnswer(text, { keepAccents = false } = {}) {
  if (!text) return ''

  let result = text
    .toLowerCase()
    .trim()
    .replace(/\[[^\]]*\]/g, '') // Remove anything in square brackets (e.g., phonetic transcription)
    .replace(/\([^)]*\)/g, '') // Remove anything in parentheses

  if (!keepAccents) {
    result = result
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '') // Remove diacritical marks
  } else {
    // Compose so visually-identical accents compare equal (e.g. e + ́ === é)
    result = result.normalize('NFC')
  }

  return result
    .replace(/[.,!?;:'"()\-]/g, '') // Remove punctuation
    .replace(/\s+/g, ' ') // Normalize whitespace
    .trim()
}

/**
 * Calculate Levenshtein distance between two strings
 */
export function levenshteinDistance(a, b) {
  const matrix = Array.from({ length: a.length + 1 }, (_, i) =>
    Array.from({ length: b.length + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0))
  )

  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      if (a[i - 1] === b[j - 1]) {
        matrix[i][j] = matrix[i - 1][j - 1]
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j] + 1, // deletion
          matrix[i][j - 1] + 1, // insertion
          matrix[i - 1][j - 1] + 1 // substitution
        )
      }
    }
  }

  return matrix[a.length][b.length]
}

/**
 * Check if user's answer matches the correct answer.
 * Returns: 'exact', 'close', or 'wrong'
 * - exact: perfect match (after normalization)
 * - close: minor differences (let user decide)
 * - wrong: clearly incorrect
 *
 * A correct answer may list several acceptable meanings separated by `/` or `;`
 * (e.g. "la maison / le logement"). Matching ANY one of them counts as correct.
 *
 * @param {string} userAnswer
 * @param {string} correctAnswer
 * @param {object} [options]
 * @param {boolean} [options.strict=false] Exam grading. Accents must match
 *   exactly (café ≠ cafe) and no fuzzy/Levenshtein tolerance is applied — a
 *   result is only ever 'exact' or 'wrong', never 'close'. Other punctuation
 *   and casing are still normalized away.
 */
export function checkAnswer(userAnswer, correctAnswer, options = {}) {
  if (!userAnswer || !correctAnswer) return 'wrong'

  // If correct answer contains multiple options (separated by ; or /), check each one.
  // In every mode a single matching meaning is enough to be counted correct.
  if (correctAnswer.includes(';') || correctAnswer.includes('/')) {
    const optionList = correctAnswer.split(/[;/]/).map(o => o.trim()).filter(Boolean)
    let bestResult = 'wrong'
    for (const option of optionList) {
      const result = checkSingleAnswer(userAnswer, option, options)
      if (result === 'exact') return 'exact'
      if (result === 'close') bestResult = 'close'
    }
    return bestResult
  }

  return checkSingleAnswer(userAnswer, correctAnswer, options)
}

/**
 * Check a single answer against a single correct answer.
 */
function checkSingleAnswer(userAnswer, correctAnswer, { strict = false } = {}) {
  if (!userAnswer || !correctAnswer) return 'wrong'

  const trimmedUser = userAnswer.trim().toLowerCase()
  const trimmedCorrect = correctAnswer.trim().toLowerCase()

  // Exact match (case-insensitive, trimmed)
  if (trimmedUser === trimmedCorrect) {
    return 'exact'
  }

  // NFC normalization (compose characters) then compare
  if (trimmedUser.normalize('NFC') === trimmedCorrect.normalize('NFC')) {
    return 'exact'
  }

  // Strict (exam) grading: accents are significant, so normalize everything
  // EXCEPT the diacritical marks. Punctuation/brackets/casing are still
  // ignored. No fuzzy tolerance — either the accents match or it's wrong.
  if (strict) {
    const strictUser = normalizeAnswer(userAnswer, { keepAccents: true })
    const strictCorrect = normalizeAnswer(correctAnswer, { keepAccents: true })
    if (strictUser && strictUser === strictCorrect) {
      return 'exact'
    }
    return 'wrong'
  }

  // Normalized comparison (strips accents, punctuation, brackets)
  const normalizedUser = normalizeAnswer(userAnswer)
  const normalizedCorrect = normalizeAnswer(correctAnswer)

  if (normalizedUser === normalizedCorrect) {
    // Same word ignoring accents. If the accents ALSO match it's a true exact
    // hit; otherwise the only difference is accents (é↔e, ç↔c). In French the
    // accents matter, so a missing/wrong accent must NOT pass as correct — it
    // becomes "fast richtig" (close) so the learner sees the correct spelling
    // and decides, rather than it silently counting as right.
    const accentUser = normalizeAnswer(userAnswer, { keepAccents: true })
    const accentCorrect = normalizeAnswer(correctAnswer, { keepAccents: true })
    if (accentUser === accentCorrect) {
      return 'exact'
    }
    return 'close'
  }

  // Empty after normalization
  if (!normalizedUser || !normalizedCorrect) {
    return 'wrong'
  }

  // Check overall similarity with Levenshtein
  const distance = levenshteinDistance(normalizedUser, normalizedCorrect)
  const maxCloseDistance = Math.max(2, Math.floor(normalizedCorrect.length * 0.3))

  if (distance <= maxCloseDistance) {
    return 'close'
  }

  return 'wrong'
}
