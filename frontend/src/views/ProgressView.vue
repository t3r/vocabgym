<template>
  <!-- Progress view: Charts, stats cards, session history -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-8">Mein Fortschritt</h1>

    <LoadingSpinner v-if="isLoading" class="py-12" />

    <template v-else>
      <!-- Stats Cards -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <div class="card text-center">
          <p class="text-3xl font-bold text-primary-600">{{ stats.totalVocabSets || 0 }}</p>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">Vokabelsets</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-primary-600">{{ stats.totalWords || 0 }}</p>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">Vokabeln gesamt</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-success">{{ formatMasteryLevel(stats.averageMastery) }}</p>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">Ø Beherrschung</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-blue-500">{{ formatPercentage(stats.overallAccuracy) }}</p>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">Genauigkeit</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-warning">{{ stats.totalSessions || 0 }}</p>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">Übungen</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-orange-500">🔥 {{ stats.practiceStreak || 0 }}</p>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">Tage-Streak</p>
        </div>
      </div>

      <!-- Charts -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">Beherrschungsverteilung</h3>
          <ProgressChart v-if="masteryData" :data="masteryData" type="bar" />
          <p v-else class="text-gray-500 text-center py-8">Noch keine Daten vorhanden</p>
        </div>
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">Übungsaktivität & Genauigkeit</h3>
          <ProgressChart v-if="activityData" :data="activityData" type="line" />
          <p v-else class="text-gray-500 text-center py-8">Noch keine Daten vorhanden</p>
        </div>
      </div>

      <!-- Forecast: when will "sicher" be reached at the current pace -->
      <div
        v-if="forecast && forecast.note"
        class="card mb-8 border-l-4"
        :class="forecast.alreadySecured ? 'border-success' : 'border-primary-500'"
      >
        <div class="flex items-start gap-3">
          <span class="text-2xl" aria-hidden="true">{{ forecast.alreadySecured ? '🏆' : '🔮' }}</span>
          <div class="min-w-0">
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-1">Prognose</h3>
            <p class="text-sm text-gray-600 dark:text-gray-300">{{ forecast.note }}</p>
            <div
              v-if="!forecast.alreadySecured && forecast.securedWords != null"
              class="mt-2 text-xs text-gray-500 dark:text-gray-400"
            >
              {{ forecast.securedWords }} von {{ forecast.totalWords }} Wörtern schon „sicher“ (Stufe ≥ 4)
              <template v-if="forecast.estimatedDate">
                · Ziel etwa {{ formatForecastDate(forecast.estimatedDate) }}
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Weakest Words -->
      <div v-if="weakestWords.length" class="card mb-8">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">🎯 Schwierige Wörter</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left border-b border-gray-200 dark:border-gray-700">
                <th class="pb-2 font-medium text-gray-500 dark:text-gray-400">Wort</th>
                <th class="pb-2 font-medium text-gray-500 dark:text-gray-400">Übersetzung</th>
                <th class="pb-2 font-medium text-gray-500 dark:text-gray-400 text-center">Level</th>
                <th class="pb-2 font-medium text-gray-500 dark:text-gray-400 text-center">Genauigkeit</th>
                <th class="pb-2 font-medium text-gray-500 dark:text-gray-400 hidden sm:table-cell">Letzte Fehler</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
              <tr v-for="(word, i) in weakestWords" :key="i" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                <td class="py-2 font-medium text-gray-900 dark:text-white">{{ word.source }}</td>
                <td class="py-2 text-gray-600 dark:text-gray-300">{{ word.target }}</td>
                <td class="py-2 text-center">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="{
                      'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300': word.masteryLevel <= 1,
                      'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300': word.masteryLevel === 2,
                      'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300': word.masteryLevel === 3,
                    }">
                    {{ word.masteryLevel }}/5
                  </span>
                </td>
                <td class="py-2 text-center" :class="word.accuracy < 50 ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'">
                  {{ word.accuracy }}%
                </td>
                <td class="py-2 text-xs text-gray-400 dark:text-gray-500 hidden sm:table-cell">
                  <span v-if="word.recentErrors.length">
                    {{ word.recentErrors.join(', ') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Session History -->
      <div class="card">
        <h3 class="text-lg font-semibold mb-4">Letzte Übungen</h3>
        <SessionHistory :sessions="recentSessions" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import { formatPercentage } from '@/utils/formatters'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ProgressChart from '@/components/progress/ProgressChart.vue'
import SessionHistory from '@/components/progress/SessionHistory.vue'

const isLoading = ref(true)
const stats = ref({})
const masteryData = ref(null)
const activityData = ref(null)
const recentSessions = ref([])
const weakestWords = ref([])
const forecast = ref(null)

// averageMastery is a 0–5 level, NOT a percentage. Show it as "x.x / 5"
// (previously it was fed through formatPercentage, which wrongly rendered
// e.g. level 4.2 as "4%").
function formatMasteryLevel(value) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(1)} / 5`
}

// ISO date (YYYY-MM-DD) → "TT.MM.JJJJ" for the forecast target date.
function formatForecastDate(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

onMounted(async () => {
  try {
    const response = await api.get('/progress/overview')
    const data = response.data

    stats.value = {
      totalVocabSets: data.totalVocabSets || 0,
      totalWords: data.totalWords || 0,
      averageMastery: data.averageMastery || 0,
      overallAccuracy: data.overallAccuracy || 0,
      totalSessions: data.totalSessions || 0,
      practiceStreak: data.practiceStreak || 0,
    }

    recentSessions.value = data.recentSessions || []
    weakestWords.value = data.weakestWords || []
    forecast.value = data.forecast || null

    // Build mastery distribution chart from backend data
    const dist = data.masteryDistribution
    if (dist) {
      masteryData.value = {
        labels: ['Neu (0)', 'Stufe 1', 'Stufe 2', 'Stufe 3', 'Stufe 4', 'Beherrscht (5)'],
        datasets: [{
          label: 'Vokabeln',
          data: [
            dist['0'] || 0,
            dist['1'] || 0,
            dist['2'] || 0,
            dist['3'] || 0,
            dist['4'] || 0,
            dist['5'] || 0
          ],
          backgroundColor: ['#ef4444', '#f97316', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981']
        }]
      }
    }

    // Build activity chart. Prefer the backend's daily-aggregated series
    // (last 30 days over ALL sessions) so the history isn't limited to the last
    // 10 sessions (which for a heavy same-day user collapsed to a single point).
    // Fall back to grouping recentSessions if the backend didn't provide it.
    const activityByDay = data.activityByDay || []
    if (activityByDay.length > 0) {
      const labelOf = (isoDate) => {
        const [y, m, d] = isoDate.split('-')
        return `${d}.${m}`
      }
      activityData.value = {
        labels: activityByDay.map((p) => labelOf(p.date)),
        datasets: [
          {
            label: 'Richtige Antworten',
            data: activityByDay.map((p) => p.correct || 0),
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: true,
            tension: 0.3,
            yAxisID: 'y',
          },
          {
            label: 'Genauigkeit %',
            data: activityByDay.map((p) => p.accuracy || 0),
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            borderDash: [5, 5],
            fill: false,
            tension: 0.3,
            yAxisID: 'y1',
          },
        ],
      }
    } else if (recentSessions.value.length > 0) {
      const dateStats = {}
      for (const session of recentSessions.value) {
        if (!session.completedAt) continue
        const date = new Date(Number(session.completedAt) * 1000)
        const key = date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })
        if (!dateStats[key]) {
          dateStats[key] = { correct: 0, total: 0 }
        }
        dateStats[key].correct += (session.correct || 0)
        dateStats[key].total += (session.total || 0)
      }

      const dates = Object.keys(dateStats)
      if (dates.length > 0) {
        activityData.value = {
          labels: dates,
          datasets: [
            {
              label: 'Richtige Antworten',
              data: dates.map(d => dateStats[d].correct),
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              fill: true,
              tension: 0.3,
              yAxisID: 'y',
            },
            {
              label: 'Genauigkeit %',
              data: dates.map(d => {
                const s = dateStats[d]
                return s.total > 0 ? Math.round(s.correct / s.total * 100) : 0
              }),
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderDash: [5, 5],
              fill: false,
              tension: 0.3,
              yAxisID: 'y1',
            },
          ],
        }
      }
    }
  } catch {
    // Fail silently - show empty state
  } finally {
    isLoading.value = false
  }
})
</script>
