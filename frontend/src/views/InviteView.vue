<template>
  <div class="min-h-[60vh] flex items-center justify-center px-4">
    <div class="max-w-md w-full text-center">
      <!-- Loading -->
      <LoadingSpinner v-if="isLoading" class="py-12" />

      <!-- Valid Invite -->
      <div v-else-if="inviteValid" class="card py-10">
        <div class="text-5xl mb-4">📖💪</div>
        <h1 class="text-2xl font-bold text-gray-900 mb-2">VocabGym</h1>
        <p class="text-lg text-gray-700 mb-6">{{ message }}</p>
        <p class="text-sm text-gray-500 mb-8">
          Trainiere deine französischen Vokabeln mit deinen Klassenkameraden.
        </p>
        <button @click="handleSignUp" class="btn-primary w-full text-lg py-3">
          Jetzt registrieren
        </button>
      </div>

      <!-- Expired Invite -->
      <div v-else-if="inviteExpired" class="card py-10">
        <div class="text-5xl mb-4">⏰</div>
        <h1 class="text-xl font-bold text-gray-900 mb-2">Link abgelaufen</h1>
        <p class="text-gray-600">{{ message }}</p>
      </div>

      <!-- Invalid Invite -->
      <div v-else class="card py-10">
        <div class="text-5xl mb-4">❌</div>
        <h1 class="text-xl font-bold text-gray-900 mb-2">Ungültiger Link</h1>
        <p class="text-gray-600">{{ message }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { initiateLogin } from '@/services/cognito'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const props = defineProps({
  token: { type: String, required: true }
})

const isLoading = ref(true)
const inviteValid = ref(false)
const inviteExpired = ref(false)
const message = ref('')

onMounted(async () => {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
    const response = await axios.get(`${baseUrl}/invite/${props.token}`)
    const data = response.data

    inviteValid.value = data.valid
    inviteExpired.value = data.expired
    message.value = data.message
  } catch {
    inviteValid.value = false
    inviteExpired.value = false
    message.value = 'Ungültiger Einladungslink.'
  } finally {
    isLoading.value = false
  }
})

function handleSignUp() {
  initiateLogin()
}
</script>
