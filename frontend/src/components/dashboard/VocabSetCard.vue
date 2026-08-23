<template>
  <div class="card hover:shadow-lg transition-shadow cursor-pointer" @click="$emit('view', vocabSet)">
    <!-- Title and Metadata -->
    <div class="mb-3">
      <h3 class="font-semibold text-gray-900 truncate">{{ vocabSet.title || 'Unbenanntes Set' }}</h3>
      <p class="text-sm text-gray-500 mt-1">
        {{ vocabSet.itemCount || 0 }} Vokabeln
        <span v-if="vocabSet.metadata?.chapter"> · Kap. {{ vocabSet.metadata.chapter }}</span>
      </p>
    </div>

    <!-- Progress Bar -->
    <div class="mb-3">
      <div class="flex justify-between text-xs text-gray-500 mb-1">
        <span>Beherrschung</span>
        <span>{{ formatPercentage(vocabSet.mastery || 0) }}</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div
          class="h-2 rounded-full transition-all duration-300"
          :class="masteryColorClass"
          :style="{ width: `${vocabSet.mastery || 0}%` }"
        ></div>
      </div>
    </div>

    <!-- Last Practiced -->
    <p class="text-xs text-gray-400 mb-4">
      {{ vocabSet.lastPracticedAt ? `Zuletzt geübt: ${formatRelativeTime(vocabSet.lastPracticedAt)}` : 'Noch nicht geübt' }}
    </p>

    <!-- Actions -->
    <div class="flex gap-2" @click.stop>
      <button @click="$emit('practice', vocabSet)" class="btn-primary text-xs px-3 py-1.5 flex-1">
        Üben
      </button>
      <button @click="$emit('view', vocabSet)" class="btn-secondary text-xs px-3 py-1.5">
        Anzeigen
      </button>
      <button
        @click="$emit('delete', vocabSet)"
        class="text-gray-400 hover:text-error p-1.5 rounded-md hover:bg-red-50 transition-colors"
        aria-label="Löschen"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatPercentage, formatRelativeTime } from '@/utils/formatters'

const props = defineProps({
  vocabSet: { type: Object, required: true }
})

defineEmits(['practice', 'view', 'delete'])

const masteryColorClass = computed(() => {
  const mastery = props.vocabSet.mastery || 0
  if (mastery >= 80) return 'bg-success'
  if (mastery >= 50) return 'bg-warning'
  return 'bg-error'
})
</script>
