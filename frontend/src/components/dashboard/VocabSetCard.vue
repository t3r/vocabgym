<template>
  <div class="card hover:shadow-lg transition-shadow cursor-pointer" @click="$emit('view', vocabSet)">
    <!-- Title and Metadata -->
    <div class="mb-3 flex items-center gap-3">
      <div class="relative flex-shrink-0">
        <img
          v-if="vocabSet.identiconUrl"
          :src="vocabSet.identiconUrl"
          alt="Set-Symbol"
          class="w-12 h-12 rounded-lg bg-gray-50 dark:bg-gray-700"
          :class="{ 'opacity-60': vocabSet.mastered }"
          loading="lazy"
        />
        <!-- Mastered: a big green checkmark celebrates the fully learned set. -->
        <span
          v-if="vocabSet.mastered"
          class="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-success text-white flex items-center justify-center ring-2 ring-white dark:ring-gray-800 shadow"
          aria-label="Abgeschlossen"
          title="Komplett gelernt!"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </span>
      </div>
      <div class="min-w-0">
        <h3 class="font-semibold text-gray-900 dark:text-white truncate flex items-center gap-1.5">
          <span class="truncate">{{ vocabSet.title || 'Unbenanntes Set' }}</span>
          <span v-if="vocabSet.mastered" class="text-success flex-shrink-0" aria-hidden="true">✓</span>
        </h3>
        <p class="text-sm text-gray-500 mt-1">
          {{ vocabSet.itemCount || 0 }} Vokabeln
          <span v-if="vocabSet.metadata?.chapter"> · Kap. {{ vocabSet.metadata.chapter }}</span>
        </p>
        <!-- Async extraction status badge -->
        <span
          v-if="statusBadge"
          class="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded text-xs font-medium"
          :class="statusBadge.class"
        >{{ statusBadge.label }}</span>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="mb-3">
      <div class="flex justify-between text-xs text-gray-500 mb-1">
        <span>Beherrschung</span>
        <span v-if="vocabSet.mastered" class="font-semibold text-success">✓ Geschafft!</span>
        <span v-else>{{ formatPercentage(vocabSet.mastery || 0) }}</span>
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
        class="text-gray-400 hover:text-error p-1.5 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
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

// Badge for async extraction state. 'approved' sets show nothing (normal).
const statusBadge = computed(() => {
  const s = props.vocabSet.extractionStatus
  if (s === 'processing' || s === 'pending') {
    return { label: '⏳ Wird verarbeitet', class: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' }
  }
  if (s === 'review') {
    return { label: '✅ Bereit zum Prüfen', class: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' }
  }
  if (s === 'failed') {
    return { label: '⚠️ Fehler', class: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' }
  }
  return null
})
</script>
