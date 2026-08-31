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
import { computed, onMounted } from 'vue'
import { useVocabStore } from '@/stores/vocab'

const vocabStore = useVocabStore()

// Milestones = fully learned (mastered) sets, newest first, that have an avatar.
// "mastered" comes from the backend (every item at masteryLevel >= 4), the same
// definition that triggers the big milestone celebration.
const approvedSets = computed(() =>
  [...vocabStore.vocabSets]
    .filter((s) => s.mastered)
    .sort((a, b) => (b.lastPracticedAt || 0) - (a.lastPracticedAt || 0))
)

onMounted(() => {
  // Reuse cached list if already loaded (e.g. from dashboard); else fetch.
  if (!vocabStore.vocabSets.length) {
    vocabStore.fetchVocabSets().catch(() => {})
  }
})
</script>
