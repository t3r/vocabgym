<template>
  <!-- Progress view: Charts, stats cards, session history -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-8">Mein Fortschritt</h1>

    <LoadingSpinner v-if="isLoading" class="py-12" />

    <template v-else>
      <!-- Stats Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div class="card text-center">
          <p class="text-3xl font-bold text-primary-600">{{ stats.totalVocabSets || 0 }}</p>
          <p class="text-sm text-gray-600 mt-1">Vokabelsets</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-primary-600">{{ stats.totalWords || 0 }}</p>
          <p class="text-sm text-gray-600 mt-1">Vokabeln gesamt</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-success">{{ formatPercentage(stats.averageMastery) }}</p>
          <p class="text-sm text-gray-600 mt-1">Ø Beherrschung</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-warning">{{ stats.totalSessions || 0 }}</p>
          <p class="text-sm text-gray-600 mt-1">Übungssitzungen</p>
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
          <h3 class="text-lg font-semibold mb-4">Übungsaktivität</h3>
          <ProgressChart v-if="activityData" :data="activityData" type="line" />
          <p v-else class="text-gray-500 text-center py-8">Noch keine Daten vorhanden</p>
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

onMounted(async () => {
  try {
    const response = await api.get('/progress/overview')
    const data = response.data

    stats.value = {
      totalVocabSets: data.totalVocabSets || 0,
      totalWords: data.totalWords || 0,
      averageMastery: data.averageMastery || 0,
      totalSessions: data.totalSessions || 0
    }

    recentSessions.value = data.recentSessions || []

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

    // Build activity chart from recent sessions (group by date)
    if (recentSessions.value.length > 0) {
      const sessionsByDate = {}
      for (const session of recentSessions.value) {
        if (!session.completedAt) continue
        const date = new Date(Number(session.completedAt) * 1000)
        const key = date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })
        sessionsByDate[key] = (sessionsByDate[key] || 0) + (session.correct || 0)
      }

      const dates = Object.keys(sessionsByDate)
      if (dates.length > 0) {
        activityData.value = {
          labels: dates,
          datasets: [{
            label: 'Richtige Antworten',
            data: dates.map(d => sessionsByDate[d]),
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: true,
            tension: 0.3
          }]
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
