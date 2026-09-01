import { describe, it, expect, beforeEach, vi } from 'vitest'

// localStorage mock (jsdom in this project doesn't expose one globally).
const _ls = {}
globalThis.localStorage = {
  getItem: (k) => (k in _ls ? _ls[k] : null),
  setItem: (k, v) => { _ls[k] = String(v) },
  removeItem: (k) => { delete _ls[k] },
  clear: () => { Object.keys(_ls).forEach((k) => delete _ls[k]) },
}

// window.location mock to observe the logout redirect.
let locationHref = '/dashboard'
globalThis.window = globalThis.window || {}
globalThis.window.location = { get href() { return locationHref }, set href(v) { locationHref = v } }

// Mock the cognito refresh call.
vi.mock('@/services/cognito', () => ({
  refreshTokens: vi.fn(),
}))

// Mock axios so we control what the underlying client does per request.
const requestInterceptors = []
const responseInterceptors = []
let handler // function(config) -> Promise, set per test to simulate the server
const mockClient = vi.fn((config) => handler(config))
mockClient.interceptors = {
  request: { use: (fn) => requestInterceptors.push(fn) },
  response: { use: (onOk, onErr) => responseInterceptors.push({ onOk, onErr }) },
}
vi.mock('axios', () => ({
  default: { create: () => mockClient },
}))

import { refreshTokens } from '@/services/cognito'

// Build a JWT with a given exp (seconds since epoch).
function jwt(expSeconds, kind = 'id') {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({ token_use: kind, exp: expSeconds }))
  return `${header}.${payload}.sig`
}
const future = () => Math.floor(Date.now() / 1000) + 3600
const nearlyExpired = () => Math.floor(Date.now() / 1000) + 30 // < 2min skew
const past = () => Math.floor(Date.now() / 1000) - 10

// Run the (single) request interceptor over a config like axios would.
async function runRequest(config) {
  let c = { headers: {}, ...config }
  for (const fn of requestInterceptors) c = await fn(c)
  return c
}
// Simulate a full request+response cycle through the response interceptor.
async function runCycle(config) {
  const c = await runRequest(config)
  try {
    return await handler(c)
  } catch (err) {
    err.config = c
    for (const { onErr } of responseInterceptors) {
      return onErr(err)
    }
    throw err
  }
}

let api
beforeEach(async () => {
  localStorage.clear()
  locationHref = '/dashboard'
  requestInterceptors.length = 0
  responseInterceptors.length = 0
  refreshTokens.mockReset()
  mockClient.mockClear()
  vi.resetModules()
  api = await import('@/services/api')
})

describe('api token handling', () => {
  it('attaches the id token as a Bearer token', async () => {
    localStorage.setItem('vocab_trainer_id_token', jwt(future()))
    const cfg = await runRequest({ url: '/x' })
    expect(cfg.headers.Authorization).toBe(`Bearer ${jwt(future())}`)
  })

  it('proactively refreshes a nearly-expired token BEFORE the request', async () => {
    localStorage.setItem('vocab_trainer_id_token', jwt(nearlyExpired()))
    localStorage.setItem('vocab_trainer_refresh_token', 'rt')
    const fresh = jwt(future())
    refreshTokens.mockResolvedValueOnce({ id_token: fresh, access_token: 'at' })

    const cfg = await runRequest({ url: '/x' })
    expect(refreshTokens).toHaveBeenCalledTimes(1)
    expect(cfg.headers.Authorization).toBe(`Bearer ${fresh}`)
    expect(localStorage.getItem('vocab_trainer_id_token')).toBe(fresh)
  })

  it('does NOT refresh a token with plenty of lifetime left', async () => {
    localStorage.setItem('vocab_trainer_id_token', jwt(future()))
    localStorage.setItem('vocab_trainer_refresh_token', 'rt')
    await runRequest({ url: '/x' })
    expect(refreshTokens).not.toHaveBeenCalled()
  })

  it('on 401, refreshes and retries with the new id token (no logout)', async () => {
    localStorage.setItem('vocab_trainer_id_token', jwt(future()))
    localStorage.setItem('vocab_trainer_refresh_token', 'rt')
    const fresh = jwt(future() + 100)
    refreshTokens.mockResolvedValueOnce({ id_token: fresh, access_token: 'at' })

    let calls = 0
    handler = vi.fn(async (config) => {
      calls += 1
      if (calls === 1) {
        const e = new Error('unauth'); e.response = { status: 401 }; e.config = config; throw e
      }
      return { status: 200, data: 'ok', _sentAuth: config.headers.Authorization }
    })

    const res = await runCycle({ url: '/practice/complete', headers: {} })
    expect(res.status).toBe(200)
    expect(res._sentAuth).toBe(`Bearer ${fresh}`)  // retried with the NEW id token
    expect(locationHref).toBe('/dashboard')         // NOT logged out
  })

  it('logs out ONLY when the refresh itself fails', async () => {
    localStorage.setItem('vocab_trainer_id_token', jwt(future()))
    localStorage.setItem('vocab_trainer_refresh_token', 'rt')
    refreshTokens.mockRejectedValueOnce(new Error('invalid_grant'))

    handler = vi.fn(async (config) => {
      const e = new Error('unauth'); e.response = { status: 401 }; e.config = config; throw e
    })

    await expect(runCycle({ url: '/x', headers: {} })).rejects.toBeTruthy()
    expect(locationHref).toBe('/')  // redirected to login
    expect(localStorage.getItem('vocab_trainer_id_token')).toBeNull()
  })

  it('a 500 does NOT trigger a refresh or logout', async () => {
    localStorage.setItem('vocab_trainer_id_token', jwt(future()))
    localStorage.setItem('vocab_trainer_refresh_token', 'rt')

    handler = vi.fn(async (config) => {
      const e = new Error('server'); e.response = { status: 500 }; e.config = config; throw e
    })

    await expect(runCycle({ url: '/practice/complete', headers: {} })).rejects.toBeTruthy()
    expect(refreshTokens).not.toHaveBeenCalled()
    expect(locationHref).toBe('/dashboard')  // still logged in
  })

  it('shares a single refresh across concurrent callers (single-flight)', async () => {
    localStorage.setItem('vocab_trainer_id_token', jwt(nearlyExpired()))
    localStorage.setItem('vocab_trainer_refresh_token', 'rt')
    let resolveRefresh
    refreshTokens.mockReturnValueOnce(new Promise((r) => { resolveRefresh = r }))

    // Two concurrent requests both see the nearly-expired token.
    const p1 = runRequest({ url: '/a' })
    const p2 = runRequest({ url: '/b' })
    resolveRefresh({ id_token: jwt(future()), access_token: 'at' })
    await Promise.all([p1, p2])

    expect(refreshTokens).toHaveBeenCalledTimes(1)  // not twice
  })
})
