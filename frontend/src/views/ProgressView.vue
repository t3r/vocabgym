<template>
  <!-- Progress view: Charts, stats cards, session history -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-2xl font-bold text-gray-900 mb-8">Mein Fortschritt</h1>

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

    // Build chart data if available
    if (data.masteryDistribution) {
      masteryData.value = {
        labels: ['Neu', 'Lernend', 'Vertraut', 'Beherrscht'],
        datasets: [{
          label: 'Vokabeln',
          data: data.masteryDistribution,
          backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981']
        }]
      }
    }

    if (data.activityHistory) {
      activityData.value = {
        labels: data.activityHistory.map((d) => d.date),
        datasets: [{
          label: 'Geübte Vokabeln',
          data: data.activityHistory.map((d) => d.count),
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.3
        }]
      }
    }
  } catch {
    // Fail silently - show empty state
  } finally {
    isLoading.value = false
  }
})
</script>
