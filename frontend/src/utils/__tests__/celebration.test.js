import { describe, it, expect } from 'vitest'
import { pickCelebration } from '@/utils/celebration'

describe('pickCelebration', () => {
  it('returns big when the set was just mastered', () => {
    expect(pickCelebration({ setJustMastered: true, score: { percentage: 60 } })).toBe('big')
  })

  it('big takes precedence over a perfect score', () => {
    expect(pickCelebration({ setJustMastered: true, score: { percentage: 100 } })).toBe('big')
  })

  it('returns small on a perfect 100% session without mastery milestone', () => {
    expect(pickCelebration({ setJustMastered: false, score: { percentage: 100 } })).toBe('small')
  })

  it('returns null on a non-perfect session with no milestone', () => {
    expect(pickCelebration({ setJustMastered: false, score: { percentage: 80 } })).toBeNull()
  })

  it('returns null when already mastered (no transition) and not perfect', () => {
    expect(pickCelebration({ setMastered: true, setJustMastered: false, score: { percentage: 90 } })).toBeNull()
  })

  it('handles missing/empty results gracefully', () => {
    expect(pickCelebration(null)).toBeNull()
    expect(pickCelebration({})).toBeNull()
    expect(pickCelebration({ score: {} })).toBeNull()
  })
})
