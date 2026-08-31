import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Celebration from '@/components/common/Celebration.vue'

// jsdom has no canvas 2d context; stub getContext so the animation path doesn't
// throw. We don't assert on drawing, only on activation/teardown behaviour.
beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(), save: vi.fn(), restore: vi.fn(),
    translate: vi.fn(), rotate: vi.fn(), fillRect: vi.fn(), scale: vi.fn(),
    set fillStyle(_) {}, set globalAlpha(_) {},
  }))
  globalThis.requestAnimationFrame = vi.fn(() => 1)
  globalThis.cancelAnimationFrame = vi.fn()
  globalThis.performance = globalThis.performance || { now: () => 0 }
})

function setReducedMotion(reduce) {
  globalThis.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: reduce,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
}

describe('Celebration.vue', () => {
  it('is inactive until celebrate() is called', () => {
    setReducedMotion(false)
    const wrapper = mount(Celebration)
    expect(wrapper.find('canvas').exists()).toBe(false)
  })

  it('activates and renders a canvas on celebrate (motion allowed)', async () => {
    setReducedMotion(false)
    const wrapper = mount(Celebration)
    wrapper.vm.celebrate('big')
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    // Animation loop scheduled
    expect(requestAnimationFrame).toHaveBeenCalled()
  })

  it('respects prefers-reduced-motion: shows a static emoji, no rAF loop', async () => {
    setReducedMotion(true)
    const wrapper = mount(Celebration)
    wrapper.vm.celebrate('big')
    await flushPromises()
    // Static fallback emoji visible, no animation loop started
    expect(wrapper.text()).toContain('🎆')
    expect(requestAnimationFrame).not.toHaveBeenCalled()
  })

  it('small intensity in reduced-motion shows confetti emoji', async () => {
    setReducedMotion(true)
    const wrapper = mount(Celebration)
    wrapper.vm.celebrate('small')
    await flushPromises()
    expect(wrapper.text()).toContain('🎉')
  })
})
