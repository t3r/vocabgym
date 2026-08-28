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
})
