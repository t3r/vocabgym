import axios from 'axios'

/**
 * Axios client with robust Cognito token handling.
 *
 * The API Gateway COGNITO_USER_POOLS authorizer reads the `Authorization`
 * header. This app authenticates with the **ID token** (it carries the
 * `cognito:groups` claim used for the teacher role), so we send the ID token —
 * consistently, as a `Bearer` token — on every request AND on every retry.
 *
 * To avoid the "silent logout mid-session" bug (a 60-minute token expiring
 * during a long practice session, causing progress loss), we:
 *   1. Refresh PROACTIVELY: before a request, if the ID token is expired or
 *      about to expire, refresh first (so the request never 401s).
 *   2. Refresh REACTIVELY on 401 and retry the original request with the new
 *      ID token.
 * Both share a single in-flight refresh (no stampede). We only log the user out
 * when the refresh itself genuinely fails (no/expired refresh token) — never on
 * a 500 or other transient error.
 */

const TOKEN_PREFIX = 'vocab_trainer_'
// Refresh when the token has less than this left (or is already expired).
const REFRESH_SKEW_MS = 2 * 60 * 1000

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// ---- token helpers -------------------------------------------------------

function getIdToken() {
  return localStorage.getItem(`${TOKEN_PREFIX}id_token`)
}

/**
 * ms until the JWT expires (negative if already expired), or null if the token
 * is missing/unparseable.
 */
export function tokenMsRemaining(token) {
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (!payload.exp) return null
    return payload.exp * 1000 - Date.now()
  } catch {
    return null
  }
}

function clearAuthAndRedirect() {
  localStorage.removeItem(`${TOKEN_PREFIX}access_token`)
  localStorage.removeItem(`${TOKEN_PREFIX}id_token`)
  localStorage.removeItem(`${TOKEN_PREFIX}refresh_token`)
  localStorage.removeItem(`${TOKEN_PREFIX}user`)
  // Guard for non-browser (test) environments.
  if (typeof window !== 'undefined' && window.location) {
    window.location.href = '/'
  }
}

// ---- single-flight refresh ----------------------------------------------

let refreshInFlight = null

/**
 * Refresh the tokens using the refresh token. Coordinated so concurrent callers
 * share ONE network refresh. Resolves with the new ID token, or throws.
 */
function refreshIdToken() {
  if (refreshInFlight) return refreshInFlight

  const inflight = (async () => {
    const refreshToken = localStorage.getItem(`${TOKEN_PREFIX}refresh_token`)
    if (!refreshToken) {
      throw new Error('No refresh token')
    }
    const { refreshTokens } = await import('@/services/cognito')
    const tokens = await refreshTokens(refreshToken)
    if (tokens.access_token) {
      localStorage.setItem(`${TOKEN_PREFIX}access_token`, tokens.access_token)
    }
    if (tokens.id_token) {
      localStorage.setItem(`${TOKEN_PREFIX}id_token`, tokens.id_token)
    }
    return tokens.id_token || getIdToken()
  })()

  refreshInFlight = inflight
  // Reset the shared marker once settled. The extra .catch on the CLEANUP chain
  // prevents this internal handler from surfacing as an unhandled rejection;
  // real callers still receive the rejection via their own await of `inflight`.
  inflight.then(
    () => { refreshInFlight = null },
    () => { refreshInFlight = null },
  )
  return inflight
}

// ---- request interceptor: attach token + proactive refresh ---------------

apiClient.interceptors.request.use(
  async (config) => {
    let token = getIdToken()

    // Proactive refresh: if the token is missing lifetime info we leave it to
    // the 401 path, but if it's expired/expiring we refresh BEFORE sending, so
    // a long session never hits a 401 mid-request.
    const remaining = tokenMsRemaining(token)
    if (token && remaining !== null && remaining <= REFRESH_SKEW_MS) {
      try {
        token = await refreshIdToken()
      } catch {
        // Refresh failed — send the (stale) token; the 401 path will handle it.
      }
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ---- response interceptor: reactive refresh + retry on 401 ---------------

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Only a 401 triggers a refresh. A 500 (or anything else) is returned as-is
    // and never logs the user out.
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        const newToken = await refreshIdToken()
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        // The refresh itself failed (no/expired refresh token) → real logout.
        clearAuthAndRedirect()
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default {
  get: (url, config) => apiClient.get(url, config),
  post: (url, data, config) => apiClient.post(url, data, config),
  put: (url, data, config) => apiClient.put(url, data, config),
  delete: (url, config) => apiClient.delete(url, config),
  client: apiClient
}

// Exported for tests.
export { refreshIdToken, getIdToken }
