/**
 * Cognito OAuth2 service using PKCE flow.
 * Handles login, callback, token management, and logout.
 */

const COGNITO_DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID
const REDIRECT_URI = import.meta.env.VITE_COGNITO_REDIRECT_URI
const LOGOUT_URI = import.meta.env.VITE_COGNITO_LOGOUT_URI

const TOKEN_PREFIX = 'vocab_trainer_'

/**
 * Generate a cryptographically random string for PKCE
 */
function generateRandomString(length = 64) {
  const array = new Uint8Array(length)
  crypto.getRandomValues(array)
  return Array.from(array, (byte) => byte.toString(36).padStart(2, '0'))
    .join('')
    .substring(0, length)
}

/**
 * Generate SHA-256 hash and encode as base64url
 */
async function generateCodeChallenge(codeVerifier) {
  const encoder = new TextEncoder()
  const data = encoder.encode(codeVerifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  const base64 = btoa(String.fromCharCode(...new Uint8Array(digest)))
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/**
 * Redirect user to Cognito hosted UI for login
 */
export async function initiateLogin() {
  const codeVerifier = generateRandomString(64)
  const codeChallenge = await generateCodeChallenge(codeVerifier)

  // Store code verifier for callback
  sessionStorage.setItem(`${TOKEN_PREFIX}code_verifier`, codeVerifier)

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    scope: 'openid email profile',
    code_challenge_method: 'S256',
    code_challenge: codeChallenge
  })

  window.location.href = `https://${COGNITO_DOMAIN}/oauth2/authorize?${params.toString()}`
}

/**
 * Exchange authorization code for tokens
 */
export async function handleCallback(code) {
  const codeVerifier = sessionStorage.getItem(`${TOKEN_PREFIX}code_verifier`)
  if (!codeVerifier) {
    throw new Error('Code verifier not found. Please try logging in again.')
  }

  const params = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
    code_verifier: codeVerifier
  })

  const response = await fetch(`https://${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: params.toString()
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.error_description || 'Token exchange failed')
  }

  const tokens = await response.json()

  // Store tokens
  localStorage.setItem(`${TOKEN_PREFIX}access_token`, tokens.access_token)
  localStorage.setItem(`${TOKEN_PREFIX}id_token`, tokens.id_token)
  localStorage.setItem(`${TOKEN_PREFIX}refresh_token`, tokens.refresh_token)

  // Clean up code verifier
  sessionStorage.removeItem(`${TOKEN_PREFIX}code_verifier`)

  return tokens
}

/**
 * Clear tokens and redirect to Cognito logout
 */
export function logout() {
  localStorage.removeItem(`${TOKEN_PREFIX}access_token`)
  localStorage.removeItem(`${TOKEN_PREFIX}id_token`)
  localStorage.removeItem(`${TOKEN_PREFIX}refresh_token`)
  localStorage.removeItem(`${TOKEN_PREFIX}user`)

  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: LOGOUT_URI
  })

  window.location.href = `https://${COGNITO_DOMAIN}/logout?${params.toString()}`
}

/**
 * Get valid access token from storage
 */
export function getAccessToken() {
  return localStorage.getItem(`${TOKEN_PREFIX}access_token`)
}

/**
 * Fetch user info from Cognito userInfo endpoint
 */
export async function getUserInfo(accessToken) {
  const token = accessToken || getAccessToken()
  if (!token) {
    throw new Error('No access token available')
  }

  const response = await fetch(`https://${COGNITO_DOMAIN}/oauth2/userInfo`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })

  if (!response.ok) {
    throw new Error('Failed to fetch user info')
  }

  const userInfo = await response.json()
  localStorage.setItem(`${TOKEN_PREFIX}user`, JSON.stringify(userInfo))
  return userInfo
}

/**
 * Check if user has valid tokens
 */
export function isAuthenticated() {
  const token = getAccessToken()
  if (!token) return false

  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp * 1000 > Date.now()
  } catch {
    return false
  }
}

/**
 * Refresh tokens using refresh token
 */
export async function refreshTokens(refreshToken) {
  const params = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: CLIENT_ID,
    refresh_token: refreshToken
  })

  const response = await fetch(`https://${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: params.toString()
  })

  if (!response.ok) {
    throw new Error('Token refresh failed')
  }

  const tokens = await response.json()

  localStorage.setItem(`${TOKEN_PREFIX}access_token`, tokens.access_token)
  if (tokens.id_token) {
    localStorage.setItem(`${TOKEN_PREFIX}id_token`, tokens.id_token)
  }

  return tokens
}
