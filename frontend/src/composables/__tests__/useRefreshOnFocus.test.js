import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { useRefreshOnFocus } from '@/composables/useRefreshOnFocus'

// Mount a throwaway component so onMounted/onBeforeUnmount hooks run.
function withComposable(refreshFn, options) {
  return mount({
    template: '<div />',
    setup() {
      useRefreshOnFocus(refreshFn, options)
      return {}
    },
  })
}

function setVisibility(state) {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  })
}

describe('useRefreshOnFocus', () => {
  beforeEach(() => {
    setVisibility('visible')
  })

  it('refreshes when the tab becomes visible again', () => {
    const fn = vi.fn()
    withComposable(fn)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('refreshes on window focus', () => {
    const fn = vi.fn()
    withComposable(fn)
    window.dispatchEvent(new Event('focus'))
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('does not refresh while the page is hidden', () => {
    const fn = vi.fn()
    withComposable(fn)
    setVisibility('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    expect(fn).not.toHaveBeenCalled()
  })

  it('throttles rapid re-focus within the cooldown window', () => {
    const fn = vi.fn()
    withComposable(fn, { cooldownMs: 10000 })
    // visibilitychange + focus fire together on a single return; only one call.
    document.dispatchEvent(new Event('visibilitychange'))
    window.dispatchEvent(new Event('focus'))
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('refreshes again after the cooldown elapses', () => {
    const fn = vi.fn()
    const now = vi.spyOn(Date, 'now')
    now.mockReturnValue(1_000_000)
    withComposable(fn, { cooldownMs: 3000 })
    document.dispatchEvent(new Event('visibilitychange'))
    expect(fn).toHaveBeenCalledTimes(1)
    // 4s later -> allowed again
    now.mockReturnValue(1_004_000)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(fn).toHaveBeenCalledTimes(2)
    now.mockRestore()
  })

  it('removes listeners on unmount', () => {
    const fn = vi.fn()
    const wrapper = withComposable(fn)
    wrapper.unmount()
    document.dispatchEvent(new Event('visibilitychange'))
    window.dispatchEvent(new Event('focus'))
    expect(fn).not.toHaveBeenCalled()
  })

  it('swallows errors from the refresh function', () => {
    const fn = vi.fn(() => { throw new Error('boom') })
    withComposable(fn)
    // Must not throw out of the event handler.
    expect(() => document.dispatchEvent(new Event('visibilitychange'))).not.toThrow()
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
