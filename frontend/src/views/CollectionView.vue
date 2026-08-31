<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Deine Sammlung</h1>
      <p class="text-gray-600 dark:text-gray-300 mt-1">
        Für jedes Set, das du komplett gelernt hast, kommt ein Avatar in deine
        Sammlung. Je mehr Sets du meisterst, desto voller wird sie! 🏆
      </p>
    </div>

    <!-- Loading -->
    <div v-if="vocabStore.isLoading" class="text-center py-16 text-gray-500 dark:text-gray-400">
      Wird geladen…
    </div>

    <!-- Empty state -->
    <div
      v-else-if="approvedSets.length === 0"
      class="text-center py-16 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg"
    >
      <p class="text-5xl mb-3">🗃️</p>
      <p class="text-gray-700 dark:text-gray-200 font-medium">Noch keine Sets gemeistert</p>
      <p class="text-gray-500 dark:text-gray-400 text-sm mt-1">
        Übe ein Set, bis du alle Vokabeln beherrschst — dann erscheint sein Avatar hier.
      </p>
      <router-link to="/dashboard" class="btn-primary inline-block mt-4">Zum Üben</router-link>
    </div>

    <template v-else>
      <!-- Count banner -->
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {{ approvedSets.length }}
        {{ approvedSets.length === 1 ? 'Avatar' : 'Avatare' }} gesammelt
      </p>

      <!-- Avatar grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <button
          v-for="set in approvedSets"
          :key="set.vocabSetId"
          @click="$router.push(`/vocab/${set.vocabSetId}`)"
          class="card flex flex-col items-center text-center p-4 hover:shadow-lg transition-shadow"
          :title="set.title || 'Unbenanntes Set'"
        >
          <img
            v-if="set.identiconUrl"
            :src="set.identiconUrl"
            :alt="`Avatar: ${set.title || 'Set'}`"
            class="w-20 h-20 rounded-lg bg-gray-50 dark:bg-gray-700"
            loading="lazy"
          />
          <div v-else class="w-20 h-20 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center text-2xl">
            🗂️
          </div>
          <p class="mt-2 text-sm font-medium text-gray-900 dark:text-white truncate w-full">
            {{ set.title || 'Unbenanntes Set' }}
          </p>
          <p class="text-xs text-gray-400">
            {{ set.itemCount || 0 }} Vokabeln
          </p>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useVocabStore } from '@/stores/vocab'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const vocabStore = useVocabStore()
const authStore = useAuthStore()

// Mastered league sets are fetched separately: GET /vocab only returns the
// caller's OWN sets, but league sets belong to the teacher. We load them via
// the league's assigned sets and keep the ones this user has mastered.
const leagueMasteredSets = ref([])

// Milestones = every set this user has fully learned (mastered), own + league,
// newest-practiced first. "mastered" comes from the backend (every item at
// masteryLevel >= 4), the same definition that triggers the big celebration.
const approvedSets = computed(() => {
  const own = vocabStore.vocabSets.filter((s) => s.mastered)
  // Dedupe: a set could appear in both lists — the own record wins.
  const ownIds = new Set(own.map((s) => s.vocabSetId))
  const league = leagueMasteredSets.value.filter((s) => !ownIds.has(s.vocabSetId))
  return [...own, ...league].sort(
    (a, b) => (b.lastPracticedAt || 0) - (a.lastPracticedAt || 0)
  )
})

async function loadLeagueMasteredSets() {
  if (!authStore.leagueId) return
  try {
    const leagueRes = await api.get(`/league/${authStore.leagueId}`)
    const league = leagueRes.data.league || leagueRes.data
    const ids = league.vocabSetIds || []
    if (!ids.length) return
    const sets = await Promise.all(
      ids.map((id) => api.get(`/vocab/${id}`).then((r) => r.data).catch(() => null))
    )
    // Keep only the league sets this user has actually mastered.
    leagueMasteredSets.value = sets.filter((s) => s && s.mastered)
  } catch {
    // Non-fatal: the collection still shows own mastered sets.
    leagueMasteredSets.value = []
  }
}

onMounted(() => {
  // Reuse cached list if already loaded (e.g. from dashboard); else fetch.
  if (!vocabStore.vocabSets.length) {
    vocabStore.fetchVocabSets().catch(() => {})
  }
  loadLeagueMasteredSets()
})
</script>
