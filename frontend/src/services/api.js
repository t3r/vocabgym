import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - attach Bearer token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('vocab_trainer_id_token')
    if (token) {
      config.headers.Authorization = token
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - handle 401, refresh token, retry
let isRefreshing = false
let failedQueue = []

const processQueue = (error, token = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error)
    } else {
      resolve(token)
    }
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const refreshToken = localStorage.getItem('vocab_trainer_refresh_token')
        if (!refreshToken) {
          throw new Error('No refresh token')
        }

        const { refreshTokens } = await import('@/services/cognito')
        const tokens = await refreshTokens(refreshToken)

        localStorage.setItem('vocab_trainer_access_token', tokens.access_token)
        if (tokens.id_token) {
          localStorage.setItem('vocab_trainer_id_token', tokens.id_token)
        }

        processQueue(null, tokens.access_token)
        originalRequest.headers.Authorization = `Bearer ${tokens.access_token}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        // Clear tokens and redirect to login
        localStorage.removeItem('vocab_trainer_access_token')
        localStorage.removeItem('vocab_trainer_id_token')
        localStorage.removeItem('vocab_trainer_refresh_token')
        localStorage.removeItem('vocab_trainer_user')
        window.location.href = '/'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
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
