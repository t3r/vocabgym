<template>
  <div class="card text-center">
    <!-- Score Display -->
    <div class="mb-6">
      <div class="text-5xl font-bold mb-2" :class="scoreColorClass">
        {{ results.score.percentage }}%
      </div>
      <p class="text-gray-600 dark:text-gray-300">
        {{ results.score.correct }} von {{ results.score.total }} richtig
      </p>
      <p v-if="results.duration" class="text-sm text-gray-400 dark:text-gray-500 mt-1">
        Dauer: {{ formatDuration(results.duration) }}
      </p>
    </div>

    <!-- League Update -->
    <div v-if="results.leagueUpdate" class="mb-6 px-4 py-3 bg-primary-50 dark:bg-primary-900/20 rounded-lg border border-primary-200 dark:border-primary-800">
      <p class="text-sm font-medium text-primary-800 dark:text-primary-200">
        +{{ results.leagueUpdate.pointsAdded || results.score.correct }} Punkte für die Liga
        <span class="mx-2">|</span>
        🔥 Streak: {{ results.leagueUpdate.currentStreak || 0 }} Tage
      </p>
    </div>

    <!-- Error Pattern Analysis -->
    <div v-if="results.errorPatterns" class="mb-6 text-left">
      <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
        <h4 class="font-medium text-yellow-900 dark:text-yellow-200 mb-2 flex items-center gap-2">
          <span>💡</span> Lernhinweis
        </h4>
        <p class="text-sm text-yellow-800 dark:text-yellow-300 mb-3">{{ results.errorPatterns.summary }}</p>

        <!-- Article errors detail -->
        <div v-if="results.errorPatterns.articleErrors?.length" class="mt-3 space-y-1">
          <p class="text-xs font-medium text-yellow-700 dark:text-yellow-400">Artikel-Fehler:</p>
          <div v-for="(err, i) in results.errorPatterns.articleErrors" :key="'art-'+i" class="text-xs text-yellow-700 dark:text-yellow-400">
            <span class="line-through text-red-600 dark:text-red-400">{{ err.yourArticle }}</span>
            → <span class="font-medium text-green-700 dark:text-green-400">{{ err.correctArticle }}</span>
            {{ err.word.split(' ').slice(1).join(' ') }}
          </div>
        </div>

        <!-- Repeated errors detail -->
        <div v-if="results.errorPatterns.repeatedErrors?.length" class="mt-3 space-y-1">
          <p class="text-xs font-medium text-yellow-700 dark:text-yellow-400">Wiederholte Schwierigkeiten:</p>
          <div v-for="(err, i) in results.errorPatterns.repeatedErrors" :key="'rep-'+i" class="text-xs text-yellow-700 dark:text-yellow-400">
            <span class="font-medium">{{ err.word }}</span>
            <span class="text-gray-500 dark:text-gray-400"> ({{ err.timesWrong }}× falsch)</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Detailed Results -->
    <div v-if="results.detailedResults?.length" class="mb-6 text-left">
      <h4 class="font-medium text-gray-900 dark:text-white dark:text-gray-100 mb-3">Ergebnisse im Detail</h4>
      <div class="max-h-64 overflow-y-auto space-y-2">
        <div
          v-for="(result, index) in results.detailedResults"
          :key="index"
          class="flex items-center gap-3 px-3 py-2 rounded-md text-sm"
          :class="result.correct
            ? 'bg-green-50 dark:bg-green-900/30 text-green-900 dark:text-green-200'
            : 'bg-red-50 dark:bg-red-900/30 text-red-900 dark:text-red-200'"
        >
          <span :class="result.correct ? 'text-success' : 'text-error'">
            {{ result.correct ? '✓' : '✗' }}
          </span>
          <span class="flex-1 truncate">{{ result.correctAnswer }}</span>
          <span v-if="!result.correct" class="text-xs text-gray-500 dark:text-gray-400 truncate">
            ({{ result.userAnswer || 'übersprungen' }})
          </span>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-3 justify-center">
      <button @click="$emit('practice-again')" class="btn-primary">
        Nochmal üben
      </button>
      <button @click="$emit('back')" class="btn-secondary">
        Zum Dashboard
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatDuration } from '@/utils/formatters'

const props = defineProps({
  results: { type: Object, required: true }
})

defineEmits(['practice-again', 'back'])

const scoreColorClass = computed(() => {
  const pct = props.results.score.percentage
  if (pct >= 80) return 'text-success'
  if (pct >= 50) return 'text-warning'
  return 'text-error'
})
</script>
