import { ref } from 'vue'
import api from '@/services/api'

/**
 * Generic composable for API requests with loading/error states.
 * Usage: const { data, isLoading, error, execute } = useApi(() => api.get('/endpoint'))
 */
export function useApi(requestFn) {
  const data = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  async function execute(...args) {
    isLoading.value = true
    error.value = null

    try {
      const response = await requestFn(...args)
      data.value = response.data
      return response.data
    } catch (err) {
      error.value = err.response?.data?.message || err.message || 'Ein Fehler ist aufgetreten'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    data,
    isLoading,
    error,
    execute
  }
}

/**
 * Composable for API request with immediate execution
 */
export function useApiImmediate(requestFn) {
  const { data, isLoading, error, execute } = useApi(requestFn)

  // Execute immediately
  execute()

  return {
    data,
    isLoading,
    error,
    refresh: execute
  }
}

export { api }
