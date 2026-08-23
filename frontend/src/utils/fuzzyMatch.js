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
 */
export function normalizeAnswer(text) {
  if (!text) return ''

  return text
    .toLowerCase()
    .trim()
    .replace(/\[[^\]]*\]/g, '') // Remove anything in square brackets (e.g., phonetic transcription)
    .replace(/\([^)]*\)/g, '') // Remove anything in parentheses
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // Remove diacritical marks
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
 */
export function checkAnswer(userAnswer, correctAnswer) {
  if (!userAnswer || !correctAnswer) return 'wrong'

  // If correct answer contains multiple options (separated by ; or /), check each one
  if (correctAnswer.includes(';') || correctAnswer.includes('/')) {
    const options = correctAnswer.split(/[;/]/).map(o => o.trim()).filter(Boolean)
    let bestResult = 'wrong'
    for (const option of options) {
      const result = checkSingleAnswer(userAnswer, option)
      if (result === 'exact') return 'exact'
      if (result === 'close') bestResult = 'close'
    }
    return bestResult
  }

  return checkSingleAnswer(userAnswer, correctAnswer)
}

/**
 * Check a single answer against a single correct answer.
 */
function checkSingleAnswer(userAnswer, correctAnswer) {
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

  // Normalized comparison (strips accents, punctuation, brackets)
  const normalizedUser = normalizeAnswer(userAnswer)
  const normalizedCorrect = normalizeAnswer(correctAnswer)

  if (normalizedUser === normalizedCorrect) {
    return 'exact'
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
