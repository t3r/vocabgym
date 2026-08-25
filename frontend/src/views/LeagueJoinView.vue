<template>
  <div class="max-w-md mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="card">
      <h1 class="text-xl font-bold text-gray-900 dark:text-white mb-3">Liga beitreten</h1>
      <p class="text-gray-600 dark:text-gray-400 text-sm mb-6">
        Gib den 6-stelligen Beitrittscode ein, den du von deiner Lehrerin oder deinem Lehrer erhalten hast.
      </p>

      <div class="flex gap-3">
        <input
          v-model="code"
          type="text"
          maxlength="6"
          placeholder="Code eingeben"
          class="input flex-1 uppercase tracking-widest text-center font-mono text-lg"
          @keyup.enter="handleJoin"
          autofocus
        />
        <button @click="handleJoin" class="btn-primary" :disabled="joining || code.length < 6">
          {{ joining ? 'Beitritt...' : 'Beitreten' }}
        </button>
      </div>

      <p v-if="errorMessage" class="text-error text-sm mt-3">{{ errorMessage }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import api from '@/services/api'

const props = defineProps({
  code: { type: String, default: '' }
})

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { showSuccess } = useToast()

const code = ref('')
const joining = ref(false)
const errorMessage = ref(null)

onMounted(() => {
  // Pre-fill from route param
  if (route.params.code) {
    code.value = route.params.code.toUpperCase()
  }
})

async function handleJoin() {
  if (code.value.length < 6) return
  joining.value = true
  errorMessage.value = null
  try {
    const response = await api.post('/league/join', { joinCode: code.value.toUpperCase() })
    authStore.setLeagueId(response.data.leagueId)
    showSuccess('Erfolgreich beigetreten!')
    router.push({ name: 'League' })
  } catch (err) {
    errorMessage.value = err.response?.data?.error || 'Beitritt fehlgeschlagen. Bitte prüfe den Code.'
  } finally {
    joining.value = false
  }
}
</script>
