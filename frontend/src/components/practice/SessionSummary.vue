<template>
  <div class="card text-center">
    <!-- Score Display -->
    <div class="mb-6">
      <div class="text-5xl font-bold mb-2" :class="scoreColorClass">
        {{ results.score.percentage }}%
      </div>
      <p class="text-gray-600">
        {{ results.score.correct }} von {{ results.score.total }} richtig
      </p>
      <p v-if="results.duration" class="text-sm text-gray-400 mt-1">
        Dauer: {{ formatDuration(results.duration) }}
      </p>
    </div>

    <!-- Detailed Results -->
    <div v-if="results.detailedResults?.length" class="mb-6 text-left">
      <h4 class="font-medium text-gray-900 mb-3">Ergebnisse im Detail</h4>
      <div class="max-h-64 overflow-y-auto space-y-2">
        <div
          v-for="(result, index) in results.detailedResults"
          :key="index"
          class="flex items-center gap-3 px-3 py-2 rounded-md text-sm"
          :class="result.correct ? 'bg-green-50' : 'bg-red-50'"
        >
          <span :class="result.correct ? 'text-success' : 'text-error'">
            {{ result.correct ? '✓' : '✗' }}
          </span>
          <span class="flex-1 truncate">{{ result.correctAnswer }}</span>
          <span v-if="!result.correct" class="text-xs text-gray-500 truncate">
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
