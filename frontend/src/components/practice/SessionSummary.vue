<template>
  <div class="card text-center">
    <!-- Milestone celebration overlay (confetti/fireworks) -->
    <Celebration ref="celebration" />

    <!-- Set-mastered milestone banner -->
    <div v-if="results.setJustMastered" class="mb-6 px-4 py-3 bg-gradient-to-r from-primary-100 to-purple-100 dark:from-primary-900/40 dark:to-purple-900/40 rounded-lg border border-primary-200 dark:border-primary-800">
      <p class="text-lg font-bold text-primary-700 dark:text-primary-200">🎆 Set gemeistert!</p>
      <p class="text-sm text-gray-600 dark:text-gray-300">Du beherrschst jetzt alle Wörter dieses Sets. Weiter so!</p>
    </div>

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

    <!-- Exam mode: prominent time + comparison to the previous exam of this set -->
    <div v-if="isExam" class="mb-6 px-4 py-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
      <p class="text-xs uppercase tracking-wide text-red-600 dark:text-red-300 mb-1">⏱️ Prüfungszeit</p>
      <div class="text-4xl font-mono font-bold text-red-700 dark:text-red-300 tabular-nums">
        {{ formatDuration(results.duration || 0) }}
      </div>
      <div v-if="previousExam" class="mt-3 text-sm">
        <p class="text-gray-600 dark:text-gray-300">
          Letzte Prüfung: <span class="font-medium">{{ formatDuration(previousExam.duration) }}</span>
          · {{ previousExam.correct }}/{{ previousExam.total }} richtig
        </p>
        <p class="mt-1 font-medium" :class="deltaClass">{{ deltaText }}</p>
      </div>
      <p v-else class="mt-2 text-xs text-gray-500 dark:text-gray-400">
        Deine erste Prüfung für dieses Set — das ist deine Referenzzeit.
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
import { computed, ref, onMounted } from 'vue'
import { formatDuration } from '@/utils/formatters'
import { pickCelebration } from '@/utils/celebration'
import Celebration from '@/components/common/Celebration.vue'
import api from '@/services/api'

const props = defineProps({
  results: { type: Object, required: true }
})

defineEmits(['practice-again', 'back'])

const celebration = ref(null)

// Play the milestone celebration once when the summary appears.
onMounted(() => {
  const level = pickCelebration(props.results)
  if (level && celebration.value) {
    celebration.value.celebrate(level)
  }
})

const scoreColorClass = computed(() => {
  const pct = props.results.score.percentage
  if (pct >= 80) return 'text-success'
  if (pct >= 50) return 'text-warning'
  return 'text-error'
})

const isExam = computed(() => props.results.mode === 'exam')

// Previous exam run for the same vocab set (for progress comparison).
const previousExam = ref(null)

onMounted(async () => {
  if (!isExam.value || !props.results.vocabSetId) return
  try {
    const response = await api.get('/progress/overview')
    const sessions = response.data?.recentSessions || []
    const currentSessionId = props.results.sessionId
    // Most recent completed EXAM session for this set, excluding the current one.
    const prior = sessions
      .filter((s) => s.mode === 'exam'
        && s.vocabSetId === props.results.vocabSetId
        && s.sessionId !== currentSessionId
        && (s.duration || 0) > 0)
      .sort((a, b) => (b.completedAt || 0) - (a.completedAt || 0))
    if (prior.length) {
      previousExam.value = {
        duration: prior[0].duration,
        correct: prior[0].correct,
        total: prior[0].total,
      }
    }
  } catch {
    // Comparison is best-effort; ignore failures.
  }
})

const deltaText = computed(() => {
  if (!previousExam.value) return ''
  const cur = props.results.duration || 0
  const prev = previousExam.value.duration || 0
  const diff = cur - prev
  if (diff < 0) return `🚀 ${formatDuration(-diff)} schneller als beim letzten Mal!`
  if (diff > 0) return `🐢 ${formatDuration(diff)} langsamer als beim letzten Mal.`
  return 'Gleiche Zeit wie beim letzten Mal.'
})

const deltaClass = computed(() => {
  if (!previousExam.value) return ''
  const diff = (props.results.duration || 0) - (previousExam.value.duration || 0)
  if (diff < 0) return 'text-green-700 dark:text-green-400'
  if (diff > 0) return 'text-orange-600 dark:text-orange-400'
  return 'text-gray-600 dark:text-gray-300'
})
</script>
