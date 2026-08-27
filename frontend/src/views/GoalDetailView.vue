<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <LoadingSpinner v-if="loading" class="py-12" />

    <template v-else-if="goal">
      <!-- Back link -->
      <router-link to="/dashboard" class="text-sm text-primary-600 hover:text-primary-700 mb-4 inline-block">
        ← Zurück zum Dashboard
      </router-link>

      <!-- Header -->
      <div class="flex items-start justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">🎯 {{ goal.title }}</h1>
          <div class="flex items-center gap-3 mt-2">
            <span class="text-sm text-gray-500 dark:text-gray-400">
              {{ deadlineText }}
            </span>
            <span
              class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              :class="statusBadgeClass"
            >
              {{ statusLabel }}
            </span>
          </div>
        </div>
        <button
          v-if="goal.userId === currentUserId"
          @click="confirmDelete"
          class="btn-secondary text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
        >
          Löschen
        </button>
      </div>

      <!-- Overall Progress -->
      <div class="card mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Gesamtfortschritt</h2>
          <span class="text-2xl font-bold" :class="progressTextClass">
            {{ Math.round(goal.progressPercent || 0) }}%
          </span>
        </div>
        <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="progressBarClass"
            :style="{ width: `${Math.min(100, Math.round(goal.progressPercent || 0))}%` }"
          ></div>
        </div>
        <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
          {{ goal.masteredWords || 0 }} von {{ goal.totalWords || 0 }} Wörtern gemeistert
          (Ziel: Level {{ goal.targetMastery || 4 }})
        </p>
      </div>

      <!-- Recommendation -->
      <div
        v-if="goal.recommendation"
        class="rounded-lg border p-4 mb-6"
        :class="recommendationClasses"
      >
        <p class="text-sm font-medium">
          💡 {{ goal.recommendation }}
        </p>
        <p v-if="goal.requiredPerDay" class="text-xs mt-1 opacity-75">
          Empfohlen: ~{{ Math.ceil(goal.requiredPerDay) }} Wörter pro Tag
        </p>
      </div>

      <!-- Per-Set Breakdown -->
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Vokabelsets</h2>
      <div class="space-y-4 mb-8">
        <div v-for="set in (goal.perSet || [])" :key="set.vocabSetId" class="card">
          <div class="flex items-center justify-between mb-2">
            <h3 class="font-medium text-gray-900 dark:text-white">{{ set.title || set.vocabSetId }}</h3>
            <router-link
              :to="{ name: 'Practice', params: { vocabSetId: set.vocabSetId } }"
              class="btn-primary text-xs px-3 py-1.5"
            >
              Üben
            </router-link>
          </div>
          <div class="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400 mb-2">
            <span>{{ set.masteredWords || 0 }} / {{ set.totalWords || 0 }} gemeistert</span>
          </div>
          <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-500"
              :class="setProgressBarClass(set)"
              :style="{ width: `${setPercent(set)}%` }"
            ></div>
          </div>
        </div>
        <div v-if="!goal.perSet?.length" class="card text-center py-6 text-gray-500 dark:text-gray-400">
          Keine Vokabelsets in diesem Lernziel.
        </div>
      </div>

      <!-- Teacher: Member Progress -->
      <template v-if="isTeacher && goal.leagueId && memberProgress.length">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Schülerfortschritt</h2>
        <div class="card mb-6">
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
            {{ onTrackCount }} von {{ memberProgress.length }} Schülern im Zeitplan
          </p>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                  <th class="pb-2 pr-4">Name</th>
                  <th class="pb-2 pr-4">Fortschritt</th>
                  <th class="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="member in memberProgress"
                  :key="member.userId"
                  class="border-b border-gray-100 dark:border-gray-700 last:border-0"
                >
                  <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
                    {{ member.displayName || 'Unbekannt' }}
                  </td>
                  <td class="py-2 pr-4">
                    <div class="flex items-center gap-2">
                      <div class="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden max-w-[120px]">
                        <div
                          class="h-full rounded-full"
                          :class="memberProgressBarClass(member.status)"
                          :style="{ width: `${Math.min(100, Math.round(member.progressPercent || 0))}%` }"
                        ></div>
                      </div>
                      <span class="text-gray-600 dark:text-gray-400">{{ Math.round(member.progressPercent || 0) }}%</span>
                    </div>
                  </td>
                  <td class="py-2">
                    <span
                      class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                      :class="memberStatusBadgeClass(member.status)"
                    >
                      {{ memberStatusLabel(member.status) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>

    <!-- Error state -->
    <div v-else class="card text-center py-12">
      <p class="text-gray-600 dark:text-gray-300">Lernziel nicht gefunden.</p>
      <router-link to="/dashboard" class="btn-primary mt-4 inline-block">Zum Dashboard</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import api from '@/services/api'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const props = defineProps({
  goalId: { type: String, required: true }
})

const router = useRouter()
const authStore = useAuthStore()
const { showSuccess, showError } = useToast()

const loading = ref(true)
const goal = ref(null)
const memberProgress = ref([])

const currentUserId = computed(() => authStore.user?.sub || authStore.user?.userId || '')
const isTeacher = computed(() => authStore.role === 'teacher')

const onTrackCount = computed(() =>
  memberProgress.value.filter(m => m.status === 'on_track' || m.status === 'completed').length
)

const deadlineText = computed(() => {
  if (!goal.value) return ''
  const days = goal.value.daysRemaining
  if (days === undefined || days === null) {
    // Fallback: calculate from deadline string
    if (goal.value.deadline) {
      const dl = new Date(goal.value.deadline)
      const now = new Date()
      const diff = Math.ceil((dl - now) / 86400000)
      return formatDaysText(diff)
    }
    return ''
  }
  return formatDaysText(days)
})

function formatDaysText(days) {
  if (days < 0) return `📅 ${Math.abs(days)} ${Math.abs(days) === 1 ? 'Tag' : 'Tage'} überfällig`
  if (days === 0) return '📅 Heute fällig'
  return `📅 Noch ${days} ${days === 1 ? 'Tag' : 'Tage'}`
}

const statusLabel = computed(() => {
  const labels = {
    on_track: 'Im Zeitplan',
    at_risk: 'Gefährdet',
    behind: 'Im Rückstand',
    completed: 'Abgeschlossen',
    expired: 'Abgelaufen'
  }
  return labels[goal.value?.status] || goal.value?.status || ''
})

const statusBadgeClass = computed(() => {
  switch (goal.value?.status) {
    case 'on_track': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
    case 'at_risk': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
    case 'behind': return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
    case 'completed': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
    case 'expired': return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
  }
})

const progressTextClass = computed(() => {
  switch (goal.value?.status) {
    case 'on_track':
    case 'completed':
      return 'text-green-600 dark:text-green-400'
    case 'at_risk':
      return 'text-yellow-600 dark:text-yellow-400'
    case 'behind':
      return 'text-red-600 dark:text-red-400'
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

const recommendationClasses = computed(() => {
  switch (goal.value?.status) {
    case 'on_track':
    case 'completed':
      return 'bg-green-50 border-green-300 text-green-800 dark:bg-green-900/20 dark:border-green-700 dark:text-green-200'
    case 'at_risk':
      return 'bg-yellow-50 border-yellow-300 text-yellow-800 dark:bg-yellow-900/20 dark:border-yellow-700 dark:text-yellow-200'
    case 'behind':
      return 'bg-red-50 border-red-300 text-red-800 dark:bg-red-900/20 dark:border-red-700 dark:text-red-200'
    default:
      return 'bg-gray-50 border-gray-300 text-gray-700 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-300'
  }
})

function setPercent(set) {
  if (!set.totalWords) return 0
  return Math.min(100, Math.round(((set.masteredWords || 0) / set.totalWords) * 100))
}

function setProgressBarClass(set) {
  const pct = setPercent(set)
  if (pct >= 100) return 'bg-green-500 dark:bg-green-400'
  if (pct >= 50) return 'bg-yellow-500 dark:bg-yellow-400'
  return 'bg-red-500 dark:bg-red-400'
}

function memberProgressBarClass(status) {
  switch (status) {
    case 'on_track':
    case 'completed':
      return 'bg-green-500 dark:bg-green-400'
    case 'at_risk':
      return 'bg-yellow-500 dark:bg-yellow-400'
    case 'behind':
      return 'bg-red-500 dark:bg-red-400'
    default:
      return 'bg-gray-400 dark:bg-gray-500'
  }
}

function memberStatusBadgeClass(status) {
  switch (status) {
    case 'on_track': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
    case 'at_risk': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
    case 'behind': return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
    case 'completed': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
    case 'expired': return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
  }
}

function memberStatusLabel(status) {
  const labels = {
    on_track: 'Im Zeitplan',
    at_risk: 'Gefährdet',
    behind: 'Im Rückstand',
    completed: 'Abgeschlossen',
    expired: 'Abgelaufen'
  }
  return labels[status] || status || ''
}

async function confirmDelete() {
  if (!confirm('Möchtest du dieses Lernziel wirklich löschen?')) return
  try {
    await api.delete(`/goals/${props.goalId}`)
    showSuccess('Lernziel gelöscht')
    router.push({ name: 'Dashboard' })
  } catch {
    showError('Fehler beim Löschen des Lernziels')
  }
}

onMounted(async () => {
  try {
    const res = await api.get(`/goals/${props.goalId}`)
    const data = res.data.goal || res.data
    // Flatten progress sub-object into goal for easy template access
    if (data.progress) {
      Object.assign(data, data.progress)
    }
    goal.value = data

    // If teacher and league goal, load member progress
    if (isTeacher.value && goal.value.leagueId) {
      try {
        const membersRes = await api.get(`/goals/${props.goalId}/members`)
        memberProgress.value = membersRes.data.members || membersRes.data || []
      } catch {
        // Member progress load failure is non-critical
      }
    }
  } catch {
    goal.value = null
  } finally {
    loading.value = false
  }
})
</script>
