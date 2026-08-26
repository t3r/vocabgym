import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

/**
 * Composable for authentication state and actions.
 */
export function useAuth() {
  const authStore = useAuthStore()

  const user = computed(() => authStore.user)
  const isAuthenticated = computed(() => authStore.isAuthenticated)
  const isLoading = computed(() => authStore.isLoading)
  const error = computed(() => authStore.error)

  const userName = computed(() => {
    if (!authStore.user) return ''
    return localStorage.getItem('vocab_trainer_displayName') || authStore.user.name || ''
  })

  const userInitials = computed(() => {
    const name = userName.value
    if (!name) return '?'
    return name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .substring(0, 2)
  })

  function login() {
    authStore.login()
  }

  function logout() {
    authStore.logout()
  }

  async function handleCallback(code) {
    return authStore.handleAuthCallback(code)
  }

  function checkAuth() {
    authStore.loadUserFromStorage()
  }

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    userName,
    userInitials,
    login,
    logout,
    handleCallback,
    checkAuth
  }
}
