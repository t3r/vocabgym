<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <LoadingSpinner />
    </div>

    <!-- Has League: Show leaderboard -->
    <template v-else-if="authStore.leagueId && league">
      <!-- League Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ league.name }}</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {{ league.memberCount || 0 }} Teilnehmer · Score-Modus: {{ scoreModeLabel(league.scoreMode) }}
        </p>
      </div>

      <!-- Own Stats Banner -->
      <div v-if="ownEntry" class="card mb-6 bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="text-center">
              <div class="text-2xl font-bold text-primary-700 dark:text-primary-300">#{{ ownEntry.rank }}</div>
              <div class="text-xs text-primary-600 dark:text-primary-400">Rang</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ ownEntry.score }}</div>
              <div class="text-xs text-gray-600 dark:text-gray-400">Punkte</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-orange-600 dark:text-orange-400">🔥 {{ ownEntry.currentStreak || 0 }}</div>
              <div class="text-xs text-gray-600 dark:text-gray-400">Tage</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Leaderboard -->
      <div class="card mb-6">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Rangliste</h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                <th class="pb-2 pr-4">Rang</th>
                <th class="pb-2 pr-4">Name</th>
                <th class="pb-2 pr-4">Score</th>
                <th class="pb-2">🔥 Streak</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in leaderboard"
                :key="entry.userId"
                class="border-b border-gray-200 dark:border-gray-700 last:border-0"
                :class="entry.userId === currentUserId ? 'bg-primary-50 dark:bg-primary-900/20' : ''"
              >
                <td class="py-2 pr-4 font-medium">{{ entry.rank }}</td>
                <td class="py-2 pr-4">{{ entry.displayName || 'Unbekannt' }}</td>
                <td class="py-2 pr-4 font-medium">{{ entry.score }}</td>
                <td class="py-2">{{ entry.currentStreak || 0 }} Tage</td>
              </tr>
              <tr v-if="!leaderboard.length">
                <td colspan="4" class="py-4 text-center text-gray-500 dark:text-gray-400">
                  Noch keine Einträge
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- League Vocab Sets - Quick Practice -->
      <div v-if="leagueVocabSets.length" class="card mb-6">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Jetzt üben</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div
            v-for="set in leagueVocabSets"
            :key="set.vocabSetId"
            class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
          >
            <div>
              <p class="font-medium text-gray-900 dark:text-white text-sm">{{ set.title || 'Unbenanntes Set' }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">{{ set.itemCount || 0 }} Vokabeln</p>
            </div>
            <router-link
              :to="{ name: 'Practice', params: { vocabSetId: set.vocabSetId } }"
              class="btn-primary text-xs px-3 py-1.5"
            >
              Üben
            </router-link>
          </div>
        </div>
      </div>
      <div v-else-if="authStore.role !== 'teacher'" class="card mb-6">
        <p class="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
          Noch keine Vokabelsets zugewiesen. Deine Lehrkraft wird bald Sets freischalten.
        </p>
      </div>

      <!-- Teacher Management Section -->
      <template v-if="authStore.role === 'teacher'">
        <!-- Join Code -->
        <div class="card mb-6">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Beitrittscode</h3>
          <div class="flex items-center gap-3">
            <code class="text-2xl font-mono font-bold tracking-widest text-primary-700 dark:text-primary-300 bg-gray-100 dark:bg-gray-700 px-4 py-2 rounded">
              {{ league.joinCode }}
            </code>
            <button @click="copyJoinCode" class="btn-secondary text-sm">
              {{ joinCodeCopied ? '✓ Kopiert' : 'Kopieren' }}
            </button>
          </div>
        </div>

        <!-- Score Mode -->
        <div class="card mb-6">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Score-Modus</h3>
          <div class="flex items-center gap-3">
            <select v-model="selectedScoreMode" class="input flex-1">
              <option value="total">Gesamtzahl Richtige</option>
              <option value="weekly">Wöchentlich</option>
              <option value="accuracy">Genauigkeit</option>
              <option value="combined">Kombiniert</option>
            </select>
            <button @click="updateScoreMode" class="btn-primary text-sm" :disabled="savingScoreMode">
              {{ savingScoreMode ? 'Speichert...' : 'Speichern' }}
            </button>
          </div>
        </div>

        <!-- Assign Vocab Sets -->
        <div class="card mb-6">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Vokabelsets zuweisen</h3>
          <div v-if="myVocabSets.length === 0" class="text-gray-500 dark:text-gray-400 text-sm">
            Keine eigenen Vokabelsets vorhanden.
          </div>
          <div v-else class="space-y-2 max-h-64 overflow-y-auto">
            <label
              v-for="set in myVocabSets"
              :key="set.vocabSetId"
              class="flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
            >
              <input
                type="checkbox"
                :value="set.vocabSetId"
                v-model="selectedVocabSetIds"
                class="rounded border-gray-300 dark:border-gray-600 text-primary-600 focus:ring-primary-500"
              />
              <span class="text-sm text-gray-900 dark:text-white">{{ set.title }}</span>
              <span class="text-xs text-gray-500 dark:text-gray-400">({{ set.itemCount || 0 }} Wörter)</span>
            </label>
          </div>
          <button @click="saveAssignedSets" class="btn-primary text-sm mt-3" :disabled="savingVocabSets">
            {{ savingVocabSets ? 'Speichert...' : 'Zuweisungen speichern' }}
          </button>
        </div>

        <!-- Manage Members -->
        <div class="card mb-6">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Teilnehmer verwalten</h3>
          <div v-if="!members.length" class="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
            Noch keine Teilnehmer
          </div>
          <div v-else class="space-y-3">
            <div
              v-for="member in members"
              :key="member.userId"
              class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
            >
              <!-- Member Summary Row (clickable) -->
              <div
                class="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                @click="toggleMemberDetail(member.userId)"
              >
                <div class="flex items-center gap-3">
                  <span class="font-medium text-gray-900 dark:text-white text-sm">
                    {{ member.displayName || 'Unbekannt' }}
                  </span>
                  <span class="text-xs bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 px-2 py-0.5 rounded-full">
                    {{ member.totalCorrect || 0 }} Punkte
                  </span>
                  <span v-if="member.currentStreak" class="text-xs text-orange-600 dark:text-orange-400">
                    🔥 {{ member.currentStreak }}
                  </span>
                </div>
                <div class="flex items-center gap-2">
                  <svg
                    class="w-4 h-4 text-gray-400 transition-transform"
                    :class="{ 'rotate-180': expandedMembers.includes(member.userId) }"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              <!-- Member Detail (expandable) -->
              <div v-if="expandedMembers.includes(member.userId)" class="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-4">
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
                  <div class="text-center">
                    <div class="text-lg font-bold text-gray-900 dark:text-white">{{ member.totalCorrect || 0 }}</div>
                    <div class="text-xs text-gray-500 dark:text-gray-400">Gesamt richtig</div>
                  </div>
                  <div class="text-center">
                    <div class="text-lg font-bold text-gray-900 dark:text-white">{{ member.totalAttempts || 0 }}</div>
                    <div class="text-xs text-gray-500 dark:text-gray-400">Gesamt versucht</div>
                  </div>
                  <div class="text-center">
                    <div class="text-lg font-bold text-gray-900 dark:text-white">
                      {{ member.totalAttempts ? Math.round((member.totalCorrect / member.totalAttempts) * 100) : 0 }}%
                    </div>
                    <div class="text-xs text-gray-500 dark:text-gray-400">Genauigkeit</div>
                  </div>
                  <div class="text-center">
                    <div class="text-lg font-bold text-gray-900 dark:text-white">{{ member.weeklyCorrect || 0 }}</div>
                    <div class="text-xs text-gray-500 dark:text-gray-400">Diese Woche</div>
                  </div>
                </div>
                <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <span>
                    Letzte Übung: {{ member.lastPracticeDate || 'Nie' }}
                  </span>
                  <span>
                    Beigetreten: {{ formatDate(member.joinedAt) }}
                  </span>
                </div>
                <div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <button
                    @click.stop="removeMember(member)"
                    class="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-xs font-medium"
                  >
                    Aus Liga entfernen
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- No League: Student Join Form -->
    <template v-else-if="authStore.role === 'student'">
      <div class="card max-w-md mx-auto">
        <h1 class="text-xl font-bold text-gray-900 dark:text-white mb-3">Liga beitreten</h1>
        <p class="text-gray-600 dark:text-gray-400 text-sm mb-6">
          Eine Liga ist eine Gruppe, in der du mit deinen Mitschülern um die Wette üben kannst.
          Frage deine Lehrerin oder deinen Lehrer nach dem Beitrittscode.
        </p>
        <div class="flex gap-3">
          <input
            v-model="joinCode"
            type="text"
            maxlength="6"
            placeholder="Code eingeben"
            class="input flex-1 uppercase tracking-widest text-center font-mono text-lg"
            @keyup.enter="handleJoin"
          />
          <button @click="handleJoin" class="btn-primary" :disabled="joining || joinCode.length < 6">
            {{ joining ? 'Beitritt...' : 'Beitreten' }}
          </button>
        </div>
        <p v-if="joinError" class="text-error text-sm mt-3">{{ joinError }}</p>
      </div>
    </template>

    <!-- No League: Teacher Create Form -->
    <template v-else-if="authStore.role === 'teacher'">
      <div class="card max-w-md mx-auto">
        <h1 class="text-xl font-bold text-gray-900 dark:text-white mb-3">Liga erstellen</h1>
        <p class="text-gray-600 dark:text-gray-400 text-sm mb-6">
          Erstelle eine Liga für deine Klasse. Deine Schüler können mit dem Beitrittscode beitreten.
        </p>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
            <input v-model="newLeagueName" type="text" placeholder="z.B. Klasse 9b Englisch" class="input w-full" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Score-Modus</label>
            <select v-model="newLeagueScoreMode" class="input w-full">
              <option value="total">Gesamtzahl Richtige</option>
              <option value="weekly">Wöchentlich</option>
              <option value="accuracy">Genauigkeit</option>
              <option value="combined">Kombiniert</option>
            </select>
          </div>
          <button @click="handleCreate" class="btn-primary w-full" :disabled="creating || !newLeagueName.trim()">
            {{ creating ? 'Erstellt...' : 'Liga erstellen' }}
          </button>
          <p v-if="createError" class="text-error text-sm">{{ createError }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import api from '@/services/api'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const authStore = useAuthStore()
const { showSuccess, showError: showToastError } = useToast()

const loading = ref(false)
const league = ref(null)
const leaderboard = ref([])
const members = ref([])
const leagueVocabSets = ref([])
const myVocabSets = ref([])

// Join form state
const joinCode = ref('')
const joining = ref(false)
const joinError = ref(null)

// Create form state
const newLeagueName = ref('')
const newLeagueScoreMode = ref('total')
const creating = ref(false)
const createError = ref(null)

// Teacher management state
const selectedScoreMode = ref('total')
const savingScoreMode = ref(false)
const selectedVocabSetIds = ref([])
const savingVocabSets = ref(false)
const joinCodeCopied = ref(false)
const expandedMembers = ref([])

const currentUserId = computed(() => authStore.user?.sub || authStore.user?.userId || '')

const ownEntry = computed(() => {
  return leaderboard.value.find(e => e.userId === currentUserId.value)
})

onMounted(async () => {
  if (authStore.leagueId) {
    await loadLeagueData()
  }
})

async function loadLeagueData() {
  loading.value = true
  try {
    const [leagueRes, leaderboardRes] = await Promise.all([
      api.get(`/league/${authStore.leagueId}`),
      api.get(`/league/${authStore.leagueId}/leaderboard`)
    ])
    league.value = leagueRes.data.league || leagueRes.data
    leaderboard.value = leaderboardRes.data.leaderboard || leaderboardRes.data || []
    selectedScoreMode.value = league.value.scoreMode || 'total'
    selectedVocabSetIds.value = league.value.vocabSetIds || []

    // Load league vocab sets for practice
    if (league.value.vocabSetIds?.length) {
      const setPromises = league.value.vocabSetIds.map(id =>
        api.get(`/vocab/${id}`).then(r => r.data).catch(() => null)
      )
      const sets = await Promise.all(setPromises)
      leagueVocabSets.value = sets.filter(Boolean)
    }

    if (authStore.role === 'teacher') {
      const [membersRes, vocabRes] = await Promise.all([
        api.get(`/league/${authStore.leagueId}/members`),
        api.get('/vocab')
      ])
      members.value = membersRes.data.members || membersRes.data || []
      myVocabSets.value = vocabRes.data.vocabSets || vocabRes.data || []
    }
  } catch (err) {
    // If league not found, clear the stored leagueId
    if (err.response?.status === 404 || err.response?.status === 403) {
      authStore.setLeagueId(null)
      league.value = null
    } else {
      showToastError('Fehler beim Laden der Liga-Daten')
    }
  } finally {
    loading.value = false
  }
}

async function handleJoin() {
  if (joinCode.value.length < 6) return
  joining.value = true
  joinError.value = null
  try {
    const response = await api.post('/league/join', { joinCode: joinCode.value.toUpperCase() })
    authStore.setLeagueId(response.data.leagueId)
    showSuccess('Erfolgreich beigetreten!')
    await loadLeagueData()
  } catch (err) {
    joinError.value = err.response?.data?.error || 'Beitritt fehlgeschlagen. Bitte Code prüfen.'
  } finally {
    joining.value = false
  }
}

async function handleCreate() {
  if (!newLeagueName.value.trim()) return
  creating.value = true
  createError.value = null
  try {
    const response = await api.post('/league', {
      name: newLeagueName.value.trim(),
      scoreMode: newLeagueScoreMode.value
    })
    authStore.setLeagueId(response.data.leagueId)
    showSuccess('Liga erfolgreich erstellt!')
    await loadLeagueData()
  } catch (err) {
    createError.value = err.response?.data?.error || 'Erstellung fehlgeschlagen.'
  } finally {
    creating.value = false
  }
}

async function updateScoreMode() {
  savingScoreMode.value = true
  try {
    await api.put(`/league/${authStore.leagueId}`, { scoreMode: selectedScoreMode.value })
    league.value.scoreMode = selectedScoreMode.value
    showSuccess('Score-Modus aktualisiert')
  } catch {
    showToastError('Fehler beim Speichern des Score-Modus')
  } finally {
    savingScoreMode.value = false
  }
}

async function saveAssignedSets() {
  savingVocabSets.value = true
  try {
    await api.put(`/league/${authStore.leagueId}`, { vocabSetIds: selectedVocabSetIds.value })
    league.value.vocabSetIds = [...selectedVocabSetIds.value]
    showSuccess('Vokabelsets zugewiesen')
  } catch {
    showToastError('Fehler beim Speichern der Zuweisungen')
  } finally {
    savingVocabSets.value = false
  }
}

async function removeMember(member) {
  const name = member.displayName || 'diesen Teilnehmer'
  if (!confirm(`Möchtest du ${name} wirklich aus der Liga entfernen?`)) return
  try {
    await api.delete(`/league/${authStore.leagueId}/members/${member.userId}`)
    members.value = members.value.filter(m => m.userId !== member.userId)
    showSuccess('Teilnehmer entfernt')
  } catch {
    showToastError('Fehler beim Entfernen des Teilnehmers')
  }
}

function toggleMemberDetail(userId) {
  const idx = expandedMembers.value.indexOf(userId)
  if (idx >= 0) {
    expandedMembers.value.splice(idx, 1)
  } else {
    expandedMembers.value.push(userId)
  }
}

async function copyJoinCode() {
  try {
    await navigator.clipboard.writeText(league.value.joinCode)
    joinCodeCopied.value = true
    setTimeout(() => { joinCodeCopied.value = false }, 3000)
  } catch {
    showToastError('Kopieren fehlgeschlagen')
  }
}

function scoreModeLabel(mode) {
  const labels = {
    total: 'Gesamtzahl Richtige',
    weekly: 'Wöchentlich',
    accuracy: 'Genauigkeit',
    combined: 'Kombiniert'
  }
  return labels[mode] || mode
}

function formatDate(timestamp) {
  if (!timestamp) return ''
  const d = new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
</script>
