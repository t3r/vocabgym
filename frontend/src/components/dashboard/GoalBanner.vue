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
import { goalStatusClass } from '@/utils/goalStatus'

const goal = ref(null)

const bannerClasses = computed(() => goalStatusClass('banner', goal.value?.status))
const titleClass = computed(() => goalStatusClass('title', goal.value?.status))
const metaClass = computed(() => goalStatusClass('meta', goal.value?.status))
const linkClass = computed(() => goalStatusClass('link', goal.value?.status))
const progressBarClass = computed(() => goalStatusClass('bar', goal.value?.status))

const deadlineText = computed(() => {
  if (!goal.value) return ''
  const days = goal.value.daysRemaining
  if (days === undefined || days === null) return ''
  // The deadline is due at 00:00 of the set day. So on the deadline day itself
  // (days === 0) the time is already up — treat it as overdue, not "today".
  if (days <= 0) return '📅 Frist abgelaufen'
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
