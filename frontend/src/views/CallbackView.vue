<template>
  <!-- OAuth callback handler: exchanges authorization code for tokens -->
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <LoadingSpinner v-if="!error" size="lg" />
      <p v-if="!error" class="mt-4 text-gray-600 dark:text-gray-300">Anmeldung wird verarbeitet...</p>

      <div v-if="error" class="card max-w-md mx-auto">
        <div class="text-error mb-4">
          <svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-2">Anmeldung fehlgeschlagen</h2>
        <p class="text-gray-600 mb-4">{{ error }}</p>
        <router-link to="/" class="btn-primary">Zurück zur Startseite</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const authStore = useAuthStore()
const error = ref(null)

onMounted(async () => {
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')
  const errorParam = urlParams.get('error')
  const errorDescription = urlParams.get('error_description')

  if (errorParam) {
    error.value = errorDescription || 'Anmeldung fehlgeschlagen'
    return
  }

  if (!code) {
    error.value = 'Kein Autorisierungscode erhalten'
    return
  }

  try {
    const success = await authStore.handleAuthCallback(code)
    if (success) {
      router.replace({ name: 'Dashboard' })
    } else {
      error.value = authStore.error || 'Anmeldung fehlgeschlagen'
    }
  } catch (err) {
    error.value = err.message || 'Ein unerwarteter Fehler ist aufgetreten'
  }
})
</script>
