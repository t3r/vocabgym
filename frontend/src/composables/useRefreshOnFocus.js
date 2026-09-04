import { onMounted, onBeforeUnmount } from 'vue'

/**
 * Re-run a refresh function whenever the user returns to the tab/window, so the
 * view shows current data without a manual F5.
 *
 * Fires when the tab becomes visible again (visibilitychange) or the window
 * regains focus. A short cooldown prevents a double refresh (both events can
 * fire on the same return) and avoids hammering the API on quick tab flips.
 *
 * Usage:
 *   const load = async () => { ... }   // your existing loader
 *   onMounted(load)                    // initial load (as before)
 *   useRefreshOnFocus(load)            // + refresh when the tab is re-focused
 *
 * @param {() => (void | Promise<void>)} refreshFn  Loader to call on re-focus.
 * @param {object} [options]
 * @param {number} [options.cooldownMs=3000]  Minimum gap between refreshes.
 */
export function useRefreshOnFocus(refreshFn, { cooldownMs = 3000 } = {}) {
  let lastRun = 0

  function maybeRefresh() {
    // Only when the page is actually visible (ignore the "hide" transition).
    if (document.visibilityState !== 'visible') return
    const now = Date.now()
    if (now - lastRun < cooldownMs) return
    lastRun = now
    try {
      // refreshFn may be async; we don't await — fire and forget. Callers are
      // expected to handle their own errors (as their onMounted loaders do).
      Promise.resolve(refreshFn()).catch(() => {})
    } catch {
      // Never let a refresh error bubble out of an event handler.
    }
  }

  function onVisibility() {
    maybeRefresh()
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('focus', maybeRefresh)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('focus', maybeRefresh)
  })
}
