<template>
  <div>
    <div v-if="sessions.length === 0" class="text-center py-6 text-gray-500 text-sm">
      Noch keine Übungssitzungen vorhanden.
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200">
            <th class="pb-2 text-left font-medium text-gray-500">Datum</th>
            <th class="pb-2 text-left font-medium text-gray-500">Vokabelset</th>
            <th class="pb-2 text-right font-medium text-gray-500">Ergebnis</th>
            <th class="pb-2 text-right font-medium text-gray-500">Dauer</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="session in sessions" :key="session.sessionId" class="border-b border-gray-50">
            <td class="py-2 text-gray-600">{{ formatDate(session.completedAt) }}</td>
            <td class="py-2 text-gray-900 font-medium">{{ session.vocabSetTitle || '—' }}</td>
            <td class="py-2 text-right">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                :class="scoreClass(session.score)"
              >
                {{ session.score || '—' }}
              </span>
            </td>
            <td class="py-2 text-right text-gray-500">{{ formatDuration(session.duration) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { formatDate, formatDuration } from '@/utils/formatters'

defineProps({
  sessions: { type: Array, default: () => [] }
})

function scoreClass(score) {
  if (!score) return 'bg-gray-100 text-gray-600'
  // Parse "18/20" format
  const parts = score.split('/')
  if (parts.length === 2) {
    const percentage = (parseInt(parts[0]) / parseInt(parts[1])) * 100
    if (percentage >= 80) return 'bg-green-100 text-green-800'
    if (percentage >= 50) return 'bg-yellow-100 text-yellow-800'
    return 'bg-red-100 text-red-800'
  }
  return 'bg-gray-100 text-gray-600'
}
</script>
