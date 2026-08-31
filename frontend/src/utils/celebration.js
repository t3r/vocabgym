/**
 * Decide which milestone celebration (if any) to play for a completed session.
 *
 * - 'big'   → the set just transitioned to fully mastered (setJustMastered).
 * - 'small' → a perfect 100% session score (but no mastery milestone).
 * - null    → nothing to celebrate.
 *
 * 'big' takes precedence over 'small'.
 *
 * @param {object} results - practice store sessionResults
 * @returns {'big'|'small'|null}
 */
export function pickCelebration(results) {
  if (!results) return null
  if (results.setJustMastered === true) return 'big'
  const pct = results.score?.percentage
  if (pct === 100) return 'small'
  return null
}
