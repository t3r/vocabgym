<template>
  <div v-if="goal" class="rounded-lg border p-4 mb-6" :class="bannerClasses">
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-lg font-semibold" :class="titleClass">🎯 {{ goal.title }}</span>
          <span v-if="goal.status === 'completed'" class="text-green-700 dark:text-green-300">✓</span>
        </div>
        <div class="flex items-center gap-3 text-sm" :class="metaClass">
          <span>{{ deadlineText }}</span>
          <span>·</span>
          <span>{{ Math.round(goal.progressPercent || 0) }}% geschafft ({{ goal.masteredWords || 0 }} von {{ goal.totalWords || 0 }} Wörtern)</span>
        </div>

        <!-- Progress bar -->
        <div class="mt-3 h-2.5 bg-white/50 dark:bg-gray-700/50 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="progressBarClass"
            :style="{ width: `${Math.min(100, Math.round(goal.progressPercent || 0))}%` }"
          ></div>
        </div>

        <!-- Recommendation -->
        <p v-if="goal.recommendation" class="mt-2 text-sm" :class="metaClass">
          💡 {{ goal.recommendation }}
        </p>
      </div>

      <router-link
        :to="{ name: 'GoalDetail', params: { goalId: goal.goalId } }"
        class="text-sm font-medium whitespace-nowrap hover:underline"
        :class="linkClass"
      >
        Details →
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const goal = ref(null)

const bannerClasses = computed(() => {
  switch (goal.value?.status) {
    case 'on_track':
    case 'completed':
      return 'bg-green-50 border-green-300 dark:bg-green-900/20 dark:border-green-700'
    case 'at_risk':
      return 'bg-yellow-50 border-yellow-300 dark:bg-yellow-900/20 dark:border-yellow-700'
    case 'behind':
      return 'bg-red-50 border-red-300 dark:bg-red-900/20 dark:border-red-700'
    default:
      return 'bg-gray-50 border-gray-300 dark:bg-gray-800 dark:border-gray-700'
  }
})

const titleClass = computed(() => {
  switch (goal.value?.status) {
    case 'on_track':
    case 'completed':
      return 'text-green-800 dark:text-green-200'
    case 'at_risk':
      return 'text-yellow-800 dark:text-yellow-200'
    case 'behind':
      return 'text-red-800 dark:text-red-200'
    default:
      return 'text-gray-800 dark:text-gray-200'
  }
})

const metaClass = computed(() => {
  switch (goal.value?.status) {
    case 'on_track':
    case 'completed':
      return 'text-green-700 dark:text-green-300'
    case 'at_risk':
      return 'text-yellow-700 dark:text-yellow-300'
    case 'behind':
      return 'text-red-700 dark:text-red-300'
    default:
      return 'text-gray-600 dark:text-gray-400'
  }
})

const linkClass = computed(() => {
  switch (goal.value?.status) {
    case 'on_track':
    case 'completed':
      return 'text-green-700 dark:text-green-300'
    case 'at_risk':
      return 'text-yellow-700 dark:text-yellow-300'
    case 'behind':
      return 'text-red-700 dark:text-red-300'
    default:
      return 'text-primary-600 dark:text-primary-400'
  }
})

const progressBarClass = computed(() => {
  switch (goal.value?.status) {
    case 'on_track':
    case 'completed':
      return 'bg-green-500 dark:bg-green-400'
    case 'at_risk':
      return 'bg-yellow-500 dark:bg-yellow-400'
    case 'behind':
      return 'bg-red-500 dark:bg-red-400'
    default:
      return 'bg-primary-500 dark:bg-primary-400'
  }
})

const deadlineText = computed(() => {
  if (!goal.value) return ''
  const days = goal.value.daysRemaining
  if (days === undefined || days === null) return ''
  if (days < 0) return '📅 Überfällig!'
  if (days === 0) return '📅 Heute fällig!'
  return `📅 Noch ${days} ${days === 1 ? 'Tag' : 'Tage'}`
})

onMounted(async () => {
  try {
    const res = await api.get('/goals')
    const goals = res.data.goals || res.data || []
    // Find first active goal (not completed, not expired)
    const active = goals.find(g => {
      const status = g.progress?.status || g.status
      return status !== 'completed' && status !== 'expired'
    })
    if (active) {
      // Flatten progress into goal for easy template access
      if (active.progress) {
        Object.assign(active, active.progress)
      }
      goal.value = active
    }
  } catch {
    // Goal loading failure is non-critical
  }
})
</script>
