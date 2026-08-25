<template>
  <div>
    <div v-if="sessions.length === 0" class="text-center py-6 text-gray-500 dark:text-gray-400 text-sm">
      Noch keine Übungssitzungen vorhanden.
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200 dark:border-gray-700">
            <th class="pb-2 text-left font-medium text-gray-500 dark:text-gray-400">Datum</th>
            <th class="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">Ergebnis</th>
            <th class="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">Dauer</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="session in sessions" :key="session.sessionId" class="border-b border-gray-100 dark:border-gray-700">
            <td class="py-2 text-gray-600 dark:text-gray-300">{{ formatSessionDate(session.completedAt) }}</td>
            <td class="py-2 text-right">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                :class="scoreClass(session)"
              >
                {{ session.correct || 0 }}/{{ session.total || 0 }}
              </span>
            </td>
            <td class="py-2 text-right text-gray-500 dark:text-gray-400">{{ formatSessionDuration(session.duration) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  sessions: { type: Array, default: () => [] }
})

function formatSessionDate(timestamp) {
  if (!timestamp) return '—'
  const date = new Date(Number(timestamp) * 1000)
  return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatSessionDuration(seconds) {
  if (!seconds) return '—'
  const s = Number(seconds)
  if (s < 60) return `${s}s`
  const min = Math.floor(s / 60)
  const sec = s % 60
  return `${min}:${String(sec).padStart(2, '0')} min`
}

function scoreClass(session) {
  const correct = session.correct || 0
  const total = session.total || 1
  const pct = (correct / total) * 100
  if (pct >= 80) return 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200'
  if (pct >= 50) return 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-800 dark:text-yellow-200'
  return 'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-200'
}
</script>
