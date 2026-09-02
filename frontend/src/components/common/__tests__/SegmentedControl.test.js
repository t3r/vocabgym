import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SegmentedControl from '@/components/common/SegmentedControl.vue'

/**
 * SegmentedControl replaces two-option dropdowns with side-by-side, radio-style
 * segments. Pins: correct selection emit, active-state marking, and keyboard
 * (arrow-key) navigation — the accessibility contract of a radiogroup.
 */
const options = [
  { value: 'a', label: 'Alpha', icon: '📚' },
  { value: 'b', label: 'Beta' },
]

function makeWrapper(modelValue = 'a') {
  return mount(SegmentedControl, {
    props: { modelValue, options, ariaLabel: 'Test' },
  })
}

describe('SegmentedControl', () => {
  it('renders one radio per option with the labels', () => {
    const wrapper = makeWrapper()
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios).toHaveLength(2)
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('Beta')
  })

  it('marks the selected option as checked', () => {
    const wrapper = makeWrapper('b')
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios[0].attributes('aria-checked')).toBe('false')
    expect(radios[1].attributes('aria-checked')).toBe('true')
  })

  it('emits update:modelValue when a different segment is clicked', async () => {
    const wrapper = makeWrapper('a')
    await wrapper.findAll('[role="radio"]')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['b'])
  })

  it('does not emit when the already-selected segment is clicked', async () => {
    const wrapper = makeWrapper('a')
    await wrapper.findAll('[role="radio"]')[0].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeFalsy()
  })

  it('selects the next option on ArrowRight', async () => {
    const wrapper = makeWrapper('a')
    await wrapper.findAll('[role="radio"]')[0].trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['b'])
  })

  it('wraps around to the first option on ArrowRight from the last', async () => {
    const wrapper = makeWrapper('b')
    await wrapper.findAll('[role="radio"]')[1].trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['a'])
  })

  it('only the selected segment is in the tab order', () => {
    const wrapper = makeWrapper('a')
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios[0].attributes('tabindex')).toBe('0')
    expect(radios[1].attributes('tabindex')).toBe('-1')
  })
})
