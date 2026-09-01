import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

// Restore auth state from localStorage BEFORE installing router.
// Awaiting ensures a stale token is refreshed & persisted before the first
// navigation guard runs and before any protected view fires an API request.
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()

authStore.loadUserFromStorage().finally(() => {
  app.use(router)
  app.mount('#app')

  // After auth is ready (so a fresh token is available), re-send any practice
  // sessions that couldn't be saved earlier due to a network drop. Fire-and-
  // forget: failures stay queued for the next load.
  if (authStore.isAuthenticated) {
    import('@/stores/practice')
      .then(({ usePracticeStore }) => usePracticeStore().recoverPendingSessions())
      .catch(() => {})
  }
})
