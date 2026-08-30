<template>
  <header class="bg-white shadow-sm border-b border-gray-200 dark:bg-gray-800 dark:border-gray-700">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2">
          <img src="/logo.svg" alt="VocabGym Logo" class="h-8 w-auto" />
          <span class="font-bold text-xl text-gray-900 dark:text-white">VocabGym</span>
        </router-link>

        <!-- Navigation Links (authenticated) -->
        <nav v-if="isAuthenticated" class="hidden md:flex items-center gap-6">
          <router-link
            to="/dashboard"
            class="text-gray-600 hover:text-gray-900 dark:text-white font-medium transition-colors dark:text-gray-300 dark:hover:text-white"
            active-class="text-primary-600 dark:text-primary-400"
          >
            Dashboard
          </router-link>
          <router-link
            to="/upload"
            class="text-gray-600 hover:text-gray-900 dark:text-white font-medium transition-colors dark:text-gray-300 dark:hover:text-white"
            active-class="text-primary-600 dark:text-primary-400"
          >
            Hochladen
          </router-link>
          <router-link
            to="/progress"
            class="text-gray-600 hover:text-gray-900 dark:text-white font-medium transition-colors dark:text-gray-300 dark:hover:text-white"
            active-class="text-primary-600 dark:text-primary-400"
          >
            Fortschritt
          </router-link>
          <router-link
            to="/league"
            class="text-gray-600 hover:text-gray-900 dark:text-white font-medium transition-colors dark:text-gray-300 dark:hover:text-white"
            active-class="text-primary-600 dark:text-primary-400"
          >
            Liga
          </router-link>
        </nav>

        <!-- User Menu -->
        <div class="flex items-center gap-3">
          <!-- Help Link -->
          <router-link
            to="/help"
            class="p-2 rounded-md text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 text-sm font-medium"
            title="Hilfe"
            aria-label="Hilfe"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </router-link>

          <!-- Dark Mode Toggle -->
          <button
            @click="toggleDarkMode"
            class="relative flex items-center w-16 h-8 rounded-full transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800"
            :class="isDark ? 'bg-gray-600' : 'bg-gray-200'"
            :aria-label="isDark ? 'Heller Modus' : 'Dunkler Modus'"
            role="switch"
            :aria-checked="isDark"
          >
            <span class="absolute left-1 text-xs">☀️</span>
            <span class="absolute right-1 text-xs">🌙</span>
            <span
              class="absolute w-6 h-6 bg-white dark:bg-gray-300 rounded-full shadow-md transform transition-transform duration-300"
              :class="isDark ? 'translate-x-9' : 'translate-x-0.5'"
            ></span>
          </button>

          <div v-if="isAuthenticated" class="flex items-center gap-3">
            <button
              @click="editingName = true"
              class="hidden sm:block text-sm text-gray-600 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 cursor-pointer"
              title="Namen ändern"
            >
              {{ userName || 'Name setzen' }}
            </button>
            <!-- Inline Name Editor -->
            <div v-if="editingName" class="fixed inset-0 z-50 flex items-start justify-center pt-20" @click.self="editingName = false">
              <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-4 w-72 border border-gray-200 dark:border-gray-700">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Anzeigename</label>
                <input
                  v-model="newDisplayName"
                  type="text"
                  maxlength="50"
                  placeholder="Dein Name"
                  class="input-field w-full text-sm mb-3"
                  @keyup.enter="saveDisplayName"
                  ref="nameInput"
                />
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Symbol-Stil</label>
                <div class="flex gap-2 mb-3">
                  <button
                    type="button"
                    @click="iconSet = 'set1'"
                    :class="iconSet === 'set1' ? 'btn-primary' : 'btn-secondary'"
                    class="text-xs flex-1"
                  >🤖 Roboter</button>
                  <button
                    type="button"
                    @click="iconSet = 'set4'"
                    :class="iconSet === 'set4' ? 'btn-primary' : 'btn-secondary'"
                    class="text-xs flex-1"
                  >🐱 Katzen</button>
                </div>
                <div class="flex gap-2">
                  <button @click="saveProfile" class="btn-primary text-xs flex-1" :disabled="!newDisplayName.trim()">Speichern</button>
                  <button @click="editingName = false" class="btn-secondary text-xs">Abbrechen</button>
                </div>
              </div>
            </div>
            <LogoutButton />
          </div>

          <!-- Login Button (unauthenticated) -->
          <LoginButton v-if="!isAuthenticated" />
        </div>

        <!-- Mobile Menu Button -->
        <button
          v-if="isAuthenticated"
          @click="toggleMobile"
          class="md:hidden p-2 rounded-md text-gray-600 hover:text-gray-900 dark:text-white hover:bg-gray-100 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-700"
          aria-label="Menü öffnen"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>

      <!-- Mobile Navigation -->
      <nav v-if="isAuthenticated && mobileMenuOpen" class="md:hidden pb-4 border-t border-gray-200 dark:border-gray-700 pt-4">
        <div class="flex flex-col gap-2">
          <router-link to="/dashboard" class="px-3 py-2 rounded-md text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700" @click="mobileMenuOpen = false">Dashboard</router-link>
          <router-link to="/upload" class="px-3 py-2 rounded-md text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700" @click="mobileMenuOpen = false">Hochladen</router-link>
          <router-link to="/progress" class="px-3 py-2 rounded-md text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700" @click="mobileMenuOpen = false">Fortschritt</router-link>
          <router-link to="/league" class="px-3 py-2 rounded-md text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700" @click="mobileMenuOpen = false">Liga</router-link>
          <router-link to="/help" class="px-3 py-2 rounded-md text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700" @click="mobileMenuOpen = false">Hilfe</router-link>
        </div>
      </nav>
    </div>
  </header>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useAuth } from '@/composables/useAuth'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'
import LoginButton from '@/components/auth/LoginButton.vue'
import LogoutButton from '@/components/auth/LogoutButton.vue'

const { isAuthenticated, userName } = useAuth()
const authStore = useAuthStore()
const mobileMenuOpen = ref(false)
const isDark = ref(false)
const editingName = ref(false)
const newDisplayName = ref('')
const iconSet = ref('set1')
const nameInput = ref(null)

watch(editingName, (val) => {
  if (val) {
    newDisplayName.value = userName.value || ''
    // Load current icon-set preference so the toggle reflects the saved value.
    api.get('/users/profile')
      .then((resp) => { iconSet.value = resp.data?.identiconSet || 'set1' })
      .catch(() => { iconSet.value = 'set1' })
    nextTick(() => nameInput.value?.focus())
  }
})

async function saveProfile() {
  const name = newDisplayName.value.trim()
  if (!name) return
  try {
    await api.put('/users/profile', { displayName: name, identiconSet: iconSet.value })
    // Update reactive store state (also persists to localStorage) so the
    // header re-renders immediately with the new name.
    authStore.setDisplayName(name)
    if (authStore.user) {
      authStore.user.name = name
    }
    editingName.value = false
  } catch {
    // Silent fail - will update on next login
    editingName.value = false
  }
}

onMounted(() => {
  // Check saved preference or system preference
  const saved = localStorage.getItem('vocabgym_dark_mode')
  if (saved !== null) {
    isDark.value = saved === 'true'
  } else {
    isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyDarkMode()
})

function toggleDarkMode() {
  isDark.value = !isDark.value
  localStorage.setItem('vocabgym_dark_mode', isDark.value.toString())
  applyDarkMode()
}

function applyDarkMode() {
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

function toggleMobile() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}
</script>
