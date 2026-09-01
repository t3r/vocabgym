import { describe, it, expect, beforeEach, vi } from 'vitest'

const _ls = {}
globalThis.localStorage = {
  getItem: (k) => (k in _ls ? _ls[k] : null),
  setItem: (k, v) => { _ls[k] = String(v) },
  removeItem: (k) => { delete _ls[k] },
  clear: () => { Object.keys(_ls).forEach((k) => delete _ls[k]) },
}

vi.mock('@/services/api', () => ({
  default: { post: vi.fn() },
}))

import api from '@/services/api'
import {
  isNetworkError,
  saveLiveSession, loadLiveSession, clearLiveSession,
  loadPending, enqueuePending, removePending,
  sendComplete, flushPending,
} from '@/services/practiceSync'

const netErr = () => { const e = new Error('net'); e.request = {}; return e }        // no response
const httpErr = (status) => { const e = new Error('http'); e.response = { status }; return e }

describe('practiceSync.isNetworkError', () => {
  it('true when a request was made but no response came back', () => {
    expect(isNetworkError(netErr())).toBe(true)
    const t = new Error('timeout'); t.code = 'ECONNABORTED'
    expect(isNetworkError(t)).toBe(true)
  })
  it('false for a real HTTP error (server responded)', () => {
    expect(isNetworkError(httpErr(500))).toBe(false)
    expect(isNetworkError(httpErr(401))).toBe(false)
  })
  it('false for null/undefined', () => {
    expect(isNetworkError(null)).toBe(false)
  })
})

describe('practiceSync live snapshot', () => {
  beforeEach(() => localStorage.clear())
  it('round-trips the live session', () => {
    saveLiveSession({ a: 1, answers: [{ x: 1 }] })
    expect(loadLiveSession()).toEqual({ a: 1, answers: [{ x: 1 }] })
    clearLiveSession()
    expect(loadLiveSession()).toBeNull()
  })
})

describe('practiceSync pending queue', () => {
  beforeEach(() => localStorage.clear())
  it('enqueues, dedupes by sessionId, and removes', () => {
    enqueuePending({ sessionId: 's1', results: [1] })
    enqueuePending({ sessionId: 's2', results: [2] })
    expect(loadPending()).toHaveLength(2)
    // same sessionId replaces, not appends
    enqueuePending({ sessionId: 's1', results: [9] })
    const list = loadPending()
    expect(list).toHaveLength(2)
    expect(list.find((p) => p.sessionId === 's1').results).toEqual([9])
    removePending('s1')
    expect(loadPending().map((p) => p.sessionId)).toEqual(['s2'])
  })
})

describe('practiceSync.sendComplete', () => {
  beforeEach(() => { localStorage.clear(); api.post.mockReset() })

  it('returns data on first success (no retry)', async () => {
    api.post.mockResolvedValueOnce({ data: { score: 80 } })
    const data = await sendComplete({ sessionId: 's', results: [] }, { sleepFn: () => Promise.resolve() })
    expect(data).toEqual({ score: 80 })
    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('retries network errors then succeeds', async () => {
    api.post
      .mockRejectedValueOnce(netErr())
      .mockRejectedValueOnce(netErr())
      .mockResolvedValueOnce({ data: { ok: true } })
    const data = await sendComplete({ sessionId: 's', results: [] },
      { attempts: 4, sleepFn: () => Promise.resolve() })
    expect(data).toEqual({ ok: true })
    expect(api.post).toHaveBeenCalledTimes(3)
  })

  it('does NOT retry a genuine HTTP error — throws immediately', async () => {
    api.post.mockRejectedValueOnce(httpErr(500))
    await expect(
      sendComplete({ sessionId: 's', results: [] }, { attempts: 4, sleepFn: () => Promise.resolve() })
    ).rejects.toBeTruthy()
    expect(api.post).toHaveBeenCalledTimes(1)  // no retry on 500
  })

  it('throws after exhausting retries on persistent network failure', async () => {
    api.post.mockRejectedValue(netErr())
    await expect(
      sendComplete({ sessionId: 's', results: [] }, { attempts: 3, sleepFn: () => Promise.resolve() })
    ).rejects.toBeTruthy()
    expect(api.post).toHaveBeenCalledTimes(3)
  })
})

describe('practiceSync.flushPending', () => {
  beforeEach(() => { localStorage.clear(); api.post.mockReset() })

  it('sends and removes a queued session on success', async () => {
    enqueuePending({ sessionId: 's1', results: [] })
    api.post.mockResolvedValueOnce({ data: {} })
    const r = await flushPending({ sleepFn: () => Promise.resolve() })
    expect(r.flushed).toBe(1)
    expect(loadPending()).toHaveLength(0)
  })

  it('keeps a session queued when the network is still down', async () => {
    enqueuePending({ sessionId: 's1', results: [] })
    api.post.mockRejectedValue(netErr())
    const r = await flushPending({ attempts: 2, sleepFn: () => Promise.resolve() })
    expect(r.flushed).toBe(0)
    expect(loadPending()).toHaveLength(1)  // stays for the next attempt
  })

  it('drops a session that fails with a permanent HTTP error', async () => {
    enqueuePending({ sessionId: 's1', results: [] })
    api.post.mockRejectedValue(httpErr(404))
    const r = await flushPending({ attempts: 2, sleepFn: () => Promise.resolve() })
    expect(r.flushed).toBe(0)
    expect(loadPending()).toHaveLength(0)  // retrying is futile → dropped
  })
})
