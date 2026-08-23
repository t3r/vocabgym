<template>
  <!-- Dashboard: Grid of vocab sets, stats overview, upload button -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Welcome and Stats -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
        Willkommen zurück{{ userName ? `, ${userName}` : '' }}!
      </h1>
      <p class="mt-1 text-gray-600 dark:text-gray-400">Hier siehst du deine Vokabelsets auf einen Blick.</p>
    </div>

    <StatsOverview class="mb-8" />

    <!-- Actions -->
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-xl font-semibold text-gray-900 dark:text-white">Meine Vokabelsets</h2>
      <div class="flex items-center gap-3">
        <button @click="generateInvite" class="btn-secondary text-sm">
          🎉 Freunde einladen
        </button>
        <router-link to="/upload" class="btn-primary">
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Neues Bild hochladen
        </router-link>
      </div>
    </div>

    <!-- Invite Link Panel -->
    <div v-if="inviteUrl" class="card mb-6 bg-blue-50 border-blue-200">
      <div class="flex items-center justify-between">
        <div>
          <p class="font-medium text-blue-900">Einladungslink</p>
          <p class="text-xs text-blue-700 mt-1">Gültig für 7 Tage</p>
        </div>
        <button @click="inviteUrl = null" class="text-blue-400 hover:text-blue-600 text-lg">✕</button>
      </div>
      <div class="mt-3 flex gap-2">
        <input
          type="text"
          :value="inviteUrl"
          readonly
          class="flex-1 text-sm bg-white border border-blue-200 rounded px-3 py-2 text-gray-700"
        />
        <button @click="copyInviteLink" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium">
          {{ copied ? '✓ Kopiert!' : 'Kopieren' }}
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <LoadingSpinner v-if="vocabStore.isLoading" class="py-12" />

    <!-- Error State -->
    <div v-else-if="vocabStore.error" class="card text-center py-8">
      <p class="text-error mb-4">{{ vocabStore.error }}</p>
      <button @click="vocabStore.fetchVocabSets()" class="btn-secondary">Erneut versuchen</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="vocabStore.sortedVocabSets.length === 0" class="card text-center py-12">
      <svg class="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
      <h3 class="text-lg font-medium text-gray-900 mb-2">Noch keine Vokabelsets</h3>
      <p class="text-gray-600 mb-6">Lade ein Bild deiner Arbeitsbuchseite hoch, um loszulegen.</p>
      <router-link to="/upload" class="btn-primary">Erstes Bild hochladen</router-link>
    </div>

    <!-- Vocab Sets Grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      <VocabSetCard
        v-for="vocabSet in vocabStore.sortedVocabSets"
        :key="vocabSet.vocabSetId"
        :vocab-set="vocabSet"
        @practice="handlePractice"
        @view="handleView"
        @delete="handleDelete"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useVocabStore } from '@/stores/vocab'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import api from '@/services/api'
import VocabSetCard from '@/components/dashboard/VocabSetCard.vue'
import StatsOverview from '@/components/dashboard/StatsOverview.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const vocabStore = useVocabStore()
const authStore = useAuthStore()
const { showError, showSuccess } = useToast()

const userName = computed(() => authStore.user?.name || authStore.user?.given_name || '')
const inviteUrl = ref(null)
const copied = ref(false)

onMounted(() => {
  vocabStore.fetchVocabSets()
})

async function generateInvite() {
  try {
    const response = await api.post('/invite')
    inviteUrl.value = response.data.inviteUrl
    copied.value = false
  } catch (err) {
    showError('Fehler beim Erstellen des Einladungslinks')
  }
}

async function copyInviteLink() {
  try {
    await navigator.clipboard.writeText(inviteUrl.value)
    copied.value = true
    showSuccess('Link in die Zwischenablage kopiert!')
    setTimeout(() => { copied.value = false }, 3000)
  } catch {
    showError('Kopieren fehlgeschlagen')
  }
}

function handlePractice(vocabSet) {
  router.push({ name: 'Practice', params: { vocabSetId: vocabSet.vocabSetId } })
}

function handleView(vocabSet) {
  router.push({ name: 'VocabSetDetail', params: { vocabSetId: vocabSet.vocabSetId } })
}

async function handleDelete(vocabSet) {
  if (!confirm(`Möchtest du "${vocabSet.title}" wirklich löschen?`)) return
  try {
    await vocabStore.deleteVocabSet(vocabSet.vocabSetId)
  } catch {
    showError('Fehler beim Löschen des Vokabelsets')
  }
}
</script>
