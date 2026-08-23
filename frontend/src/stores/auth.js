import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as cognito from '@/services/cognito'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(null)
  const idToken = ref(null)
  const refreshToken = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)

  function login() {
    cognito.initiateLogin()
  }

  async function handleAuthCallback(code) {
    isLoading.value = true
    error.value = null
    try {
      const tokens = await cognito.handleCallback(code)
      accessToken.value = tokens.access_token
      idToken.value = tokens.id_token
      refreshToken.value = tokens.refresh_token

      const userInfo = await cognito.getUserInfo(tokens.access_token)
      user.value = userInfo

      return true
    } catch (err) {
      error.value = err.message || 'Authentifizierung fehlgeschlagen'
      return false
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    user.value = null
    accessToken.value = null
    idToken.value = null
    refreshToken.value = null
    error.value = null
    cognito.logout()
  }

  async function refreshSession() {
    if (!refreshToken.value) {
      logout()
      return false
    }

    try {
      const tokens = await cognito.refreshTokens(refreshToken.value)
      accessToken.value = tokens.access_token
      idToken.value = tokens.id_token
      if (tokens.refresh_token) {
        refreshToken.value = tokens.refresh_token
      }
      return true
    } catch (err) {
      error.value = 'Sitzung abgelaufen. Bitte erneut anmelden.'
      logout()
      return false
    }
  }

  function loadUserFromStorage() {
    const storedAccessToken = localStorage.getItem('vocab_trainer_access_token')
    const storedIdToken = localStorage.getItem('vocab_trainer_id_token')
    const storedRefreshToken = localStorage.getItem('vocab_trainer_refresh_token')
    const storedUser = localStorage.getItem('vocab_trainer_user')

    if (storedAccessToken && storedUser) {
      accessToken.value = storedAccessToken
      idToken.value = storedIdToken
      refreshToken.value = storedRefreshToken
      user.value = JSON.parse(storedUser)

      checkTokenExpiry()
    }
  }

  function checkTokenExpiry() {
    if (!accessToken.value) return

    try {
      const payload = JSON.parse(atob(accessToken.value.split('.')[1]))
      const expiresAt = payload.exp * 1000
      const now = Date.now()
      const fiveMinutes = 5 * 60 * 1000

      if (now >= expiresAt) {
        refreshSession()
      } else if (now >= expiresAt - fiveMinutes) {
        refreshSession()
      }
    } catch {
      // Token format invalid, attempt refresh
      refreshSession()
    }
  }

  // Watch for token changes and persist to localStorage
  function persistTokens() {
    if (accessToken.value) {
      localStorage.setItem('vocab_trainer_access_token', accessToken.value)
    } else {
      localStorage.removeItem('vocab_trainer_access_token')
    }
    if (idToken.value) {
      localStorage.setItem('vocab_trainer_id_token', idToken.value)
    } else {
      localStorage.removeItem('vocab_trainer_id_token')
    }
    if (refreshToken.value) {
      localStorage.setItem('vocab_trainer_refresh_token', refreshToken.value)
    } else {
      localStorage.removeItem('vocab_trainer_refresh_token')
    }
    if (user.value) {
      localStorage.setItem('vocab_trainer_user', JSON.stringify(user.value))
    } else {
      localStorage.removeItem('vocab_trainer_user')
    }
  }

  // Call persistTokens when state changes
  const originalLogin = handleAuthCallback
  const wrappedHandleAuthCallback = async (code) => {
    const result = await originalLogin(code)
    persistTokens()
    return result
  }

  return {
    user,
    accessToken,
    idToken,
    refreshToken,
    isAuthenticated,
    isLoading,
    error,
    login,
    handleAuthCallback: wrappedHandleAuthCallback,
    logout: () => {
      user.value = null
      accessToken.value = null
      idToken.value = null
      refreshToken.value = null
      error.value = null
      persistTokens()
      cognito.logout()
    },
    refreshSession,
    loadUserFromStorage,
    checkTokenExpiry
  }
})
