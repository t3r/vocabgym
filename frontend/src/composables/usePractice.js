import { normalizeAnswer, checkAnswer } from '@/utils/fuzzyMatch'

/**
 * Composable for practice session logic and answer validation.
 */
export function usePractice() {
  /**
   * Check if user's answer matches the correct answer
   * Uses fuzzy matching for minor typos and accent variations
   */
  function validateAnswer(userAnswer, correctAnswer) {
    return checkAnswer(userAnswer, correctAnswer)
  }

  /**
   * Calculate score from an array of answers
   */
  function calculateScore(answers) {
    const total = answers.length
    const correct = answers.filter((a) => a.correct).length
    const incorrect = total - correct
    const percentage = total > 0 ? Math.round((correct / total) * 100) : 0

    return { total, correct, incorrect, percentage }
  }

  /**
   * Format feedback message based on correctness
   */
  function formatFeedback(isCorrect, correctAnswer) {
    if (isCorrect) {
      return {
        type: 'success',
        message: 'Richtig! 🎉',
        correctAnswer: null
      }
    }
    return {
      type: 'error',
      message: 'Leider falsch.',
      correctAnswer
    }
  }

  /**
   * Normalize answer for display comparison
   */
  function normalize(answer) {
    return normalizeAnswer(answer)
  }

  return {
    validateAnswer,
    calculateScore,
    formatFeedback,
    normalize
  }
}
