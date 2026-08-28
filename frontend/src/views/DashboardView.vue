<template>
  <!-- Dashboard: Grid of vocab sets, stats overview, upload button -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Welcome and Stats -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
        Willkommen zurück{{ userName ? `, ${userName}` : '' }}!
      </h1>
      <p class="mt-1 text-gray-600 dark:text-gray-400 dark:text-gray-500">Hier siehst du deine Vokabelsets auf einen Blick.</p>
    </div>

    <!-- League Banner -->
    <div v-if="authStore.leagueId && leagueBanner" class="card mb-6 bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <span class="text-lg font-semibold text-primary-800 dark:text-primary-200">{{ leagueBanner.name }}</span>
          <span v-if="leagueBanner.rank" class="text-sm text-gray-600 dark:text-gray-400">
            Rang #{{ leagueBanner.rank }}
          </span>
          <span v-if="leagueBanner.streak" class="text-sm text-orange-600 dark:text-orange-400">
            🔥 {{ leagueBanner.streak }} Tage
          </span>
        </div>
        <router-link to="/league" class="text-primary-600 dark:text-primary-400 text-sm font-medium hover:underline">
          Zur Liga →
        </router-link>
      </div>
    </div>

    <!-- Goal Banner -->
    <GoalBanner />

    <!-- League Vocab Sets -->
    <div v-if="authStore.leagueId && leagueVocabSets.length" class="mb-8">
      <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">Liga-Vokabeln</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="set in leagueVocabSets"
          :key="set.vocabSetId"
          class="card flex items-center justify-between"
        >
          <div>
            <h3 class="font-medium text-gray-900 dark:text-white text-sm">{{ set.title }}</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400">{{ set.itemCount || 0 }} Wörter</p>
          </div>
          <router-link
            :to="{ name: 'Practice', params: { vocabSetId: set.vocabSetId } }"
            class="btn-primary text-xs px-3 py-1"
          >
            Üben
          </router-link>
        </div>
      </div>
    </div>

    <StatsOverview class="mb-8" />

    <!-- Actions -->
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-xl font-semibold text-gray-900 dark:text-white">Meine Vokabelsets</h2>
      <div class="flex items-center gap-3">
        <button
          v-if="authStore.role === 'teacher'"
          @click="showInvite = !showInvite"
          class="btn-secondary text-sm"
        >
          ✉️ Nutzer einladen
        </button>
        <router-link to="/upload" class="btn-primary">
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Neues Bild hochladen
        </router-link>
      </div>
    </div>

    <!-- Teacher: invite a new user (no league required) -->
    <div v-if="authStore.role === 'teacher' && showInvite" class="card mb-6">
      <div class="flex items-center justify-between mb-2">
        <h3 class="font-semibold text-gray-900 dark:text-white">Nutzer einladen</h3>
        <button @click="showInvite = false" class="text-gray-400 hover:text-gray-600 text-lg">✕</button>
      </div>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-3">
        Legen Sie ein Konto für eine:n neue:n Nutzer:in an. Die Person erhält per
        E-Mail eine Einladung mit einem temporären Passwort — auch ohne Liga.
      </p>
      <form @submit.prevent="inviteUser" class="flex flex-col sm:flex-row gap-3">
        <input
          v-model="inviteEmail"
          type="email"
          placeholder="E-Mail-Adresse"
          class="input flex-1"
          :disabled="inviting"
        />
        <input
          v-model="inviteName"
          type="text"
          placeholder="Anzeigename (optional)"
          class="input flex-1"
          :disabled="inviting"
        />
        <button
          type="submit"
          class="btn-primary text-sm whitespace-nowrap"
          :disabled="inviting || !inviteEmail.trim()"
        >
          {{ inviting ? 'Wird gesendet...' : 'Einladen' }}
        </button>
      </form>
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
      <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">Noch keine Vokabelsets</h3>
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

    <!-- Version -->
    <p class="text-center text-xs text-gray-300 dark:text-gray-700 mt-8">
      {{ appVersion }}
    </p>
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
import GoalBanner from '@/components/dashboard/GoalBanner.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const vocabStore = useVocabStore()
const authStore = useAuthStore()
const { showError, showSuccess } = useToast()

const userName = computed(() => authStore.user?.name || authStore.user?.given_name || '')
const appVersion = import.meta.env.VITE_APP_VERSION || 'dev'

// Teacher: invite a new user (no league required)
const showInvite = ref(false)
const inviteEmail = ref('')
const inviteName = ref('')
const inviting = ref(false)

async function inviteUser() {
  const email = inviteEmail.value.trim()
  if (!email) return
  inviting.value = true
  try {
    await api.post('/users/invite', {
      email,
      displayName: inviteName.value.trim(),
    })
    showSuccess('Einladung wurde gesendet.')
    inviteEmail.value = ''
    inviteName.value = ''
    showInvite.value = false
  } catch (err) {
    showError(err.response?.data?.error || 'Fehler beim Einladen')
  } finally {
    inviting.value = false
  }
}

// League data
const leagueBanner = ref(null)
const leagueVocabSets = ref([])

onMounted(() => {
  vocabStore.fetchVocabSets()
  if (authStore.leagueId) {
    loadLeagueData()
  }
})

async function loadLeagueData() {
  try {
    const [leagueRes, leaderboardRes] = await Promise.all([
      api.get(`/league/${authStore.leagueId}`),
      api.get(`/league/${authStore.leagueId}/leaderboard`)
    ])
    const league = leagueRes.data.league || leagueRes.data
    const lb = leaderboardRes.data.leaderboard || leaderboardRes.data || []
    const userId = authStore.user?.sub || authStore.user?.userId
    const ownEntry = lb.find(e => e.userId === userId)

    leagueBanner.value = {
      name: league.name,
      rank: ownEntry?.rank || null,
      streak: ownEntry?.currentStreak || 0
    }

    // Load league vocab sets if any assigned
    if (league.vocabSetIds?.length) {
      const setPromises = league.vocabSetIds.map(id =>
        api.get(`/vocab/${id}`).then(r => r.data).catch(() => null)
      )
      const sets = await Promise.all(setPromises)
      leagueVocabSets.value = sets.filter(Boolean)
    }
  } catch {
    // League data load failure is non-critical
    leagueBanner.value = null
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
