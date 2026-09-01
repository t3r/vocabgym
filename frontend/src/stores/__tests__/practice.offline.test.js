import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// localStorage mock (jsdom doesn't expose one globally here).
const _ls = {}
globalThis.localStorage = {
  getItem: (k) => (k in _ls ? _ls[k] : null),
  setItem: (k, v) => { _ls[k] = String(v) },
  removeItem: (k) => { delete _ls[k] },
  clear: () => { Object.keys(_ls).forEach((k) => delete _ls[k]) },
}

// Mock the api used by both the store and practiceSync.
vi.mock('@/services/api', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))
// Make retry backoff instant in tests by stubbing sleep via a tiny delay: we
// instead rely on sendComplete's default sleep but with few attempts; to keep
// it fast we shorten attempts through the store? The store calls sendComplete
// with defaults (4 attempts). To avoid real waits, mock setTimeout to run now.
vi.stubGlobal('setTimeout', (fn) => { fn(); return 0 })

import api from '@/services/api'
import { usePracticeStore } from '@/stores/practice'
import { loadPending, loadLiveSession } from '@/services/practiceSync'

const LIVE_KEY = 'vocab_trainer_practice_live'
const PENDING_KEY = 'vocab_trainer_practice_pending'

const netErr = () => { const e = new Error('net'); e.request = {}; return e }
const httpErr = (s) => { const e = new Error('http'); e.response = { status: s }; return e }

function seedActiveSession(store) {
  store.currentSession = {
    sessionId: 'sess-1', vocabSetId: 'set-1', direction: 'de-fr',
    mode: 'practice', startTime: Date.now() - 5000,
  }
  store.questions = [{ questionId: 'q1', itemId: 'i1', correctAnswer: 'maison' }]
  store.currentQuestionIndex = 0
  store.answers = [{ itemId: 'i1', correct: true, userAnswer: 'maison', result: 'exact' }]
  store.isSessionActive = true
}

describe('practice store — offline resilience', () => {
  let store
  beforeEach(() => {
    localStorage.clear()
    api.post.mockReset()
    setActivePinia(createPinia())
    store = usePracticeStore()
  })

  it('persists the live session to localStorage on submitAnswer', () => {
    // Minimal active session so submitAnswer records + persists.
    store.currentSession = { sessionId: 's', vocabSetId: 'v', direction: 'de-fr', startTime: Date.now() }
    store.questions = [{ questionId: 'q1', itemId: 'i1', correctAnswer: 'maison' }]
    store.isSessionActive = true

    store.submitAnswer('maison')

    const snap = loadLiveSession()
    expect(snap).toBeTruthy()
    expect(snap.answers).toHaveLength(1)
    expect(snap.currentSession.sessionId).toBe('s')
  })

  it('on success: stores results, clears the live snapshot, no pending', async () => {
    seedActiveSession(store)
    localStorage.setItem(LIVE_KEY, JSON.stringify({ any: 'thing' }))
    api.post.mockResolvedValueOnce({ data: { score: 100, leagueUpdate: { totalCorrect: 1 } } })

    const res = await store.endSession()

    expect(res.savePending).toBeUndefined()
    expect(store.savePending).toBe(false)
    expect(loadPending()).toHaveLength(0)
    expect(loadLiveSession()).toBeNull()          // live snapshot cleared
    expect(store.isSessionActive).toBe(false)
  })

  it('on persistent network failure: queues pending, flags savePending, does NOT fake "saved"', async () => {
    seedActiveSession(store)
    api.post.mockRejectedValue(netErr())          // network stays down

    const res = await store.endSession()

    // The result is shown but explicitly marked as not-yet-saved.
    expect(res.savePending).toBe(true)
    expect(store.savePending).toBe(true)
    // Queued for recovery — nothing lost.
    const pending = loadPending()
    expect(pending).toHaveLength(1)
    expect(pending[0].sessionId).toBe('sess-1')
    expect(pending[0].results).toEqual([{ itemId: 'i1', correct: true, userAnswer: 'maison' }])
    expect(store.isSessionActive).toBe(false)
  })

  it('on a genuine HTTP 500: shows local results, no pending queued', async () => {
    seedActiveSession(store)
    api.post.mockRejectedValue(httpErr(500))

    const res = await store.endSession()

    expect(res.savePending).toBeUndefined()       // not a network-drop path
    expect(store.savePending).toBe(false)
    expect(loadPending()).toHaveLength(0)          // 500 is not queued
  })

  it('empty session does not POST and clears the live snapshot', async () => {
    store.currentSession = { sessionId: 's', vocabSetId: 'v', mode: 'practice', startTime: Date.now() }
    store.answers = []
    store.isSessionActive = true
    localStorage.setItem(LIVE_KEY, JSON.stringify({ any: 'thing' }))

    const res = await store.endSession()

    expect(res).toBeNull()
    expect(api.post).not.toHaveBeenCalled()
    expect(loadLiveSession()).toBeNull()
  })

  it('restoreLiveSession rebuilds an interrupted session from localStorage', () => {
    localStorage.setItem(LIVE_KEY, JSON.stringify({
      currentSession: { sessionId: 'r1', vocabSetId: 'v', direction: 'de-fr', mode: 'practice', startTime: 1 },
      questions: [{ questionId: 'q1', itemId: 'i1', correctAnswer: 'maison' }],
      currentQuestionIndex: 0,
      answers: [{ itemId: 'i1', correct: false, userAnswer: 'x', result: 'wrong' }],
      currentStreak: 0,
    }))

    const ok = store.restoreLiveSession()
    expect(ok).toBe(true)
    expect(store.isSessionActive).toBe(true)
    expect(store.currentSession.sessionId).toBe('r1')
    expect(store.answers).toHaveLength(1)
  })

  it('restoreLiveSession returns false when nothing is buffered', () => {
    expect(store.restoreLiveSession()).toBe(false)
  })
})
