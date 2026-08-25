<template>
  <div class="text-center py-8">
    <!-- Processing Animation -->
    <div v-if="status === 'processing'" class="space-y-4">
      <div class="animate-pulse">
        <svg class="w-16 h-16 text-primary-600 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <h3 class="text-lg font-medium text-gray-900 dark:text-white">Vokabeln werden extrahiert...</h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">Dies kann bis zu 30 Sekunden dauern.</p>
      <LoadingSpinner size="sm" />
    </div>

    <!-- Complete -->
    <div v-else-if="status === 'review' || status === 'approved'" class="space-y-4">
      <svg class="w-16 h-16 text-success mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <h3 class="text-lg font-medium text-gray-900 dark:text-white">Extraktion abgeschlossen!</h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">Die Vokabeln wurden erfolgreich erkannt.</p>
    </div>

    <!-- Failed -->
    <div v-else-if="status === 'failed'" class="space-y-4">
      <svg class="w-16 h-16 text-error mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <h3 class="text-lg font-medium text-gray-900 dark:text-white">Extraktion fehlgeschlagen</h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">Bitte versuche es mit einem besseren Foto erneut.</p>
    </div>

    <!-- Pending -->
    <div v-else class="space-y-4">
      <LoadingSpinner size="md" />
      <p class="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">Wird vorbereitet...</p>
    </div>
  </div>
</template>

<script setup>
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

defineProps({
  status: { type: String, default: null },
  vocabSetId: { type: String, default: null }
})

defineEmits(['complete', 'error'])
</script>
