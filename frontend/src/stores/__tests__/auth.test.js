import { describe, it, expect, beforeEach, vi } from 'vitest'

// Minimal localStorage mock (jsdom in this project doesn't expose one globally).
const _ls = {}
globalThis.localStorage = {
  getItem: (k) => (k in _ls ? _ls[k] : null),
  setItem: (k, v) => { _ls[k] = String(v) },
  removeItem: (k) => { delete _ls[k] },
  clear: () => { Object.keys(_ls).forEach((k) => delete _ls[k]) },
}

// Mock the api client (loadProfile lazily imports it) and cognito (unused here).
vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('@/services/cognito', () => ({
  initiateLogin: vi.fn(),
  handleCallback: vi.fn(),
  getUserInfo: vi.fn(),
  logout: vi.fn(),
}))

import { setActivePinia, createPinia } from 'pinia'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'

/**
 * Regression coverage for the "user is in a league but the app shows the join
 * form" incident: authStore.leagueId must be hydrated from the server profile
 * (GET /users/profile), not just localStorage — otherwise a re-login / new
 * device loses the membership client-side while the backend still has it.
 */
describe('auth store — league membership hydration (loadProfile)', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    api.get.mockReset()
  })

  it('hydrates leagueId from the profile response and persists it', async () => {
    api.get.mockResolvedValueOnce({
      data: { displayName: 'Torsten', leagueId: 'lg-123' },
    })
    const store = useAuthStore()
    expect(store.leagueId).toBeNull()

    await store.loadProfile()

    expect(store.leagueId).toBe('lg-123')
    expect(localStorage.getItem('vocab_trainer_leagueId')).toBe('lg-123')
  })

  it('clears a stale local leagueId when the server reports none (null)', async () => {
    // Simulate a device that still has an old leagueId cached locally.
    localStorage.setItem('vocab_trainer_leagueId', 'stale-old')
    setActivePinia(createPinia()) // re-init so the ref reads the stale value
    const store = useAuthStore()
    expect(store.leagueId).toBe('stale-old')

    api.get.mockResolvedValueOnce({
      data: { displayName: 'Torsten', leagueId: null },
    })
    await store.loadProfile()

    expect(store.leagueId).toBeNull()
    expect(localStorage.getItem('vocab_trainer_leagueId')).toBeNull()
  })

  it('leaves leagueId untouched when the profile omits the field entirely', async () => {
    localStorage.setItem('vocab_trainer_leagueId', 'keep-me')
    setActivePinia(createPinia())
    const store = useAuthStore()

    api.get.mockResolvedValueOnce({ data: { displayName: 'Torsten' } }) // no leagueId key
    await store.loadProfile()

    expect(store.leagueId).toBe('keep-me')
  })

  it('does not throw and leaves state intact when the profile request fails', async () => {
    localStorage.setItem('vocab_trainer_leagueId', 'lg-existing')
    setActivePinia(createPinia())
    const store = useAuthStore()

    api.get.mockRejectedValueOnce(new Error('network'))
    await expect(store.loadProfile()).resolves.toBeUndefined()

    expect(store.leagueId).toBe('lg-existing')
  })
})
