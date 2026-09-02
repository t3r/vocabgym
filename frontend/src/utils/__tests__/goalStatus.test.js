import { describe, it, expect } from 'vitest'
import { goalStatusClass, goalStatusLabel } from '@/utils/goalStatus'

/**
 * These pin the byte-for-byte class strings that GoalBanner.vue and
 * GoalDetailView.vue previously produced via inline switch statements. If any
 * string drifts, a goal's colour/label would change in the UI — this catches
 * that. green = on_track & completed, yellow = at_risk, red = behind,
 * everything else = the variant's default.
 */

describe('goalStatusLabel', () => {
  it('maps known statuses to German labels', () => {
    expect(goalStatusLabel('on_track')).toBe('Im Zeitplan')
    expect(goalStatusLabel('at_risk')).toBe('Gefährdet')
    expect(goalStatusLabel('behind')).toBe('Im Rückstand')
    expect(goalStatusLabel('completed')).toBe('Abgeschlossen')
    expect(goalStatusLabel('expired')).toBe('Abgelaufen')
  })

  it('falls back to the raw status or empty string', () => {
    expect(goalStatusLabel('weird')).toBe('weird')
    expect(goalStatusLabel(undefined)).toBe('')
  })
})

describe('goalStatusClass — colour grouping', () => {
  it('treats completed like on_track (green) across variants', () => {
    for (const v of ['banner', 'title', 'meta', 'link', 'bar', 'text', 'badge', 'recommendation', 'memberBar']) {
      expect(goalStatusClass(v, 'completed')).toBe(goalStatusClass(v, 'on_track'))
    }
  })

  it('maps at_risk→yellow, behind→red distinctly', () => {
    expect(goalStatusClass('bar', 'at_risk')).toBe('bg-yellow-500 dark:bg-yellow-400')
    expect(goalStatusClass('bar', 'behind')).toBe('bg-red-500 dark:bg-red-400')
  })

  it('uses the per-variant default for expired/unknown', () => {
    // bar/text/link default to primary; banner/badge/recommendation to gray;
    // memberBar to gray-400/500.
    expect(goalStatusClass('bar', 'expired')).toBe('bg-primary-500 dark:bg-primary-400')
    expect(goalStatusClass('link', undefined)).toBe('text-primary-600 dark:text-primary-400')
    expect(goalStatusClass('banner', 'expired')).toBe('bg-gray-50 border-gray-300 dark:bg-gray-800 dark:border-gray-700')
    expect(goalStatusClass('memberBar', 'expired')).toBe('bg-gray-400 dark:bg-gray-500')
  })

  it('returns exact badge strings (green/gray)', () => {
    expect(goalStatusClass('badge', 'on_track')).toBe('bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300')
    expect(goalStatusClass('badge', 'expired')).toBe('bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300')
  })

  it('returns empty string for an unknown variant', () => {
    expect(goalStatusClass('nope', 'on_track')).toBe('')
  })
})
