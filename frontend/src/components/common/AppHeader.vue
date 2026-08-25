<template>
  <header class="bg-white shadow-sm border-b border-gray-200 dark:bg-gray-800 dark:border-gray-700">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2">
          <svg class="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          <span class="text-lg">💪</span>
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
            class="p-2 rounded-md text-gray-500 hover:text-gray-900 dark:text-white hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-700 text-lg"
            :aria-label="isDark ? 'Heller Modus' : 'Dunkler Modus'"
            :title="isDark ? 'Heller Modus' : 'Dunkler Modus'"
          >
            {{ isDark ? '☀️' : '🌙' }}
          </button>

          <div v-if="isAuthenticated" class="flex items-center gap-3">
            <div class="hidden sm:block text-sm text-gray-600 dark:text-gray-300">
              {{ userName }}
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
import { ref, onMounted } from 'vue'
import { useAuth } from '@/composables/useAuth'
import LoginButton from '@/components/auth/LoginButton.vue'
import LogoutButton from '@/components/auth/LogoutButton.vue'

const { isAuthenticated, userName } = useAuth()
const mobileMenuOpen = ref(false)
const isDark = ref(false)

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
