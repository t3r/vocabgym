import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VocabSetCard from '@/components/dashboard/VocabSetCard.vue'

/**
 * The "mastered" checkmark is a motivational success marker: it must appear
 * only when the backend flags a set as fully learned (mastered === true), and
 * be absent otherwise. Pins both cases.
 */
function makeSet(overrides = {}) {
  return {
    vocabSetId: 's1',
    title: 'Kapitel 3',
    itemCount: 20,
    mastery: 100,
    extractionStatus: 'approved',
    ...overrides,
  }
}

describe('VocabSetCard — mastered checkmark', () => {
  it('shows the "Geschafft!" marker when the set is mastered', () => {
    const wrapper = mount(VocabSetCard, {
      props: { vocabSet: makeSet({ mastered: true }) },
    })
    expect(wrapper.text()).toContain('Geschafft!')
    // The corner checkmark badge (aria-label) is present.
    expect(wrapper.find('[aria-label="Abgeschlossen"]').exists()).toBe(true)
  })

  it('does not show the marker when the set is not mastered', () => {
    const wrapper = mount(VocabSetCard, {
      props: { vocabSet: makeSet({ mastered: false, mastery: 100 }) },
    })
    expect(wrapper.text()).not.toContain('Geschafft!')
    expect(wrapper.find('[aria-label="Abgeschlossen"]').exists()).toBe(false)
    // Falls back to showing the mastery percentage.
    expect(wrapper.text()).toContain('100')
  })
})
