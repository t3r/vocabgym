<template>
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="card text-center py-4">
      <p class="text-2xl font-bold text-primary-600">{{ stats.totalSets }}</p>
      <p class="text-xs text-gray-500 mt-1">Vokabelsets</p>
    </div>
    <div class="card text-center py-4">
      <p class="text-2xl font-bold text-primary-600">{{ stats.totalWords }}</p>
      <p class="text-xs text-gray-500 mt-1">Vokabeln</p>
    </div>
    <div class="card text-center py-4">
      <p class="text-2xl font-bold text-success">{{ stats.averageAccuracy }}%</p>
      <p class="text-xs text-gray-500 mt-1">Ø Genauigkeit</p>
    </div>
    <div class="card text-center py-4">
      <p class="text-2xl font-bold text-warning">{{ stats.practiceStreak }}</p>
      <p class="text-xs text-gray-500 mt-1">Tage Serie</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const stats = ref({
  totalSets: 0,
  totalWords: 0,
  averageAccuracy: 0,
  practiceStreak: 0
})

onMounted(async () => {
  try {
    const response = await api.get('/progress/overview')
    const data = response.data
    stats.value = {
      totalSets: data.totalVocabSets || 0,
      totalWords: data.totalWords || 0,
      averageAccuracy: Math.round(data.overallAccuracy || 0),
      practiceStreak: data.practiceStreak || 0
    }
  } catch {
    // Show zeros on error
  }
})
</script>
