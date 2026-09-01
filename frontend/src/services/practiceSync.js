import api from '@/services/api'

/**
 * Practice offline-resilience: never lose a learner's progress when the network
 * dies mid-session and comes back later.
 *
 * Two localStorage artifacts:
 *  - LIVE key: the in-progress session snapshot (questions, answers, index).
 *    Survives a reload/crash/offline so the session can be restored.
 *  - PENDING key: a queue of COMPLETED sessions whose POST /practice/complete
 *    did not go through (network error). Recovered on the next load.
 *
 * Why a separate pending queue from the token layer: a dropped network gives a
 * network error (no HTTP response), NOT a 401 — so the token-refresh interceptor
 * never fires. We must handle it explicitly here.
 */

const LIVE_KEY = 'vocab_trainer_practice_live'
const PENDING_KEY = 'vocab_trainer_practice_pending'

// Guarded localStorage access — never throw if storage is unavailable
// (private mode, SSR, test env without a mock). Resilience helpers must fail
// soft, never break the practice flow.
const store = {
  get(key) {
    try { return typeof localStorage !== 'undefined' ? localStorage.getItem(key) : null }
    catch { return null }
  },
  set(key, val) {
    try { if (typeof localStorage !== 'undefined') localStorage.setItem(key, val) }
    catch { /* full / unavailable — non-fatal */ }
  },
  remove(key) {
    try { if (typeof localStorage !== 'undefined') localStorage.removeItem(key) }
    catch { /* non-fatal */ }
  },
}

// ---- error classification -----------------------------------------------

/**
 * True for errors where the request never got an HTTP response (offline, DNS,
 * timeout, connection reset). These are retryable and must NOT be swallowed.
 * A real HTTP error (4xx/5xx) has error.response and is handled elsewhere.
 */
export function isNetworkError(err) {
  if (!err) return false
  if (err.response) return false // server responded → not a network drop
  // axios sets error.request when a request was made but no response received;
  // also treat explicit timeout/network codes as retryable.
  if (err.request) return true
  const code = err.code || ''
  return ['ECONNABORTED', 'ETIMEDOUT', 'ERR_NETWORK', 'ENETUNREACH'].includes(code)
}

// ---- live session snapshot ----------------------------------------------

export function saveLiveSession(snapshot) {
  store.set(LIVE_KEY, JSON.stringify(snapshot))
}

export function loadLiveSession() {
  try {
    const raw = store.get(LIVE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function clearLiveSession() {
  store.remove(LIVE_KEY)
}

// ---- pending completion queue -------------------------------------------

export function loadPending() {
  try {
    const raw = store.get(PENDING_KEY)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

function savePending(list) {
  store.set(PENDING_KEY, JSON.stringify(list))
}

/**
 * Queue a completed-but-unsent session. Keyed by sessionId so a later retry or
 * a duplicate never double-submits.
 */
export function enqueuePending(payload) {
  const list = loadPending()
  const idx = list.findIndex((p) => p.sessionId === payload.sessionId)
  if (idx >= 0) {
    list[idx] = payload
  } else {
    list.push(payload)
  }
  savePending(list)
}

export function removePending(sessionId) {
  savePending(loadPending().filter((p) => p.sessionId !== sessionId))
}

// ---- sending with retry --------------------------------------------------

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/**
 * POST /practice/complete with retry-and-backoff on NETWORK errors only.
 * - Resolves with the server response data on success.
 * - Throws on a genuine HTTP error (e.g. 4xx/5xx) — caller decides (that is not
 *   a "connection died" case).
 * - Throws after exhausting retries on persistent network failure; the caller
 *   is expected to have the payload queued as pending for later recovery.
 *
 * @param {{sessionId, results}} payload
 * @param {{attempts?, baseDelayMs?, sleepFn?}} opts
 */
export async function sendComplete(payload, opts = {}) {
  const attempts = opts.attempts ?? 4
  const baseDelay = opts.baseDelayMs ?? 500
  const sleepFn = opts.sleepFn ?? sleep

  let lastErr
  for (let i = 0; i < attempts; i++) {
    try {
      const resp = await api.post('/practice/complete', payload)
      return resp.data
    } catch (err) {
      lastErr = err
      if (!isNetworkError(err)) {
        // A real HTTP error is not a retryable "connection died" — surface it.
        throw err
      }
      // Network error → wait (exponential backoff) and retry, unless last try.
      if (i < attempts - 1) {
        await sleepFn(baseDelay * 2 ** i)
      }
    }
  }
  throw lastErr
}

/**
 * Try to flush every pending completed session. Called on the next load (and
 * after reconnect). Removes entries that succeed OR that fail with a genuine
 * HTTP error (those won't ever succeed by retrying); keeps entries that fail
 * with a network error for a later attempt.
 *
 * Returns { flushed, remaining }.
 */
export async function flushPending(opts = {}) {
  const list = loadPending()
  let flushed = 0
  for (const payload of list) {
    try {
      await sendComplete(payload, { attempts: opts.attempts ?? 2, ...opts })
      removePending(payload.sessionId)
      flushed += 1
    } catch (err) {
      if (!isNetworkError(err)) {
        // Permanent failure (e.g. session gone / 4xx) — drop it, retrying is futile.
        removePending(payload.sessionId)
      }
      // Network error → leave it queued for the next attempt.
    }
  }
  return { flushed, remaining: loadPending().length }
}
