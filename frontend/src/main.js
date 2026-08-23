import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

// Restore auth state from localStorage BEFORE installing router
// This ensures the first navigation guard has access to auth state
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
authStore.loadUserFromStorage()

app.use(router)

app.mount('#app')
