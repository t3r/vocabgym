<template>
  <!-- Vocab Set Detail: Full vocabulary list, practice/edit actions, stats -->
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <LoadingSpinner v-if="isLoading" class="py-12" />

    <template v-else-if="vocabSet">
      <!-- Header -->
      <div class="mb-6 flex items-start justify-between">
        <div>
          <router-link to="/dashboard" class="text-sm text-primary-600 hover:text-primary-700 mb-2 inline-block">
            ← Zurück zum Dashboard
          </router-link>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ vocabSet.title || 'Unbenanntes Set' }}</h1>
          <p class="text-gray-600 mt-1">
            {{ vocabSet.itemCount || items.length }} Vokabeln
            <span v-if="vocabSet.metadata?.chapter"> · Kapitel {{ vocabSet.metadata.chapter }}</span>
            <span v-if="vocabSet.metadata?.topic"> · {{ vocabSet.metadata.topic }}</span>
          </p>
        </div>
        <div class="flex gap-2">
          <button @click="showAddPage = !showAddPage" class="btn-secondary">
            📄 Seite hinzufügen
          </button>
          <button @click="showGoalModal = true" class="btn-secondary">
            🎯 Lernziel
          </button>
          <router-link
            :to="{ name: 'Review', params: { vocabSetId } }"
            class="btn-secondary"
          >
            Bearbeiten
          </router-link>
          <router-link
            :to="{ name: 'Practice', params: { vocabSetId } }"
            class="btn-primary"
          >
            Üben
          </router-link>
        </div>
      </div>

      <!-- Add Page Panel -->
      <div v-if="showAddPage" class="card mb-6">
        <h3 class="font-semibold text-gray-900 dark:text-white mb-3">Weitere Seite hinzufügen</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Die extrahierten Vokabeln werden zu diesem Set hinzugefügt.</p>
        <ImageDropzone
          :vocab-set-id="vocabSetId"
          @upload-success="handleAddPage"
        />
        <div v-if="addingPage" class="mt-4 flex items-center gap-3">
          <svg class="animate-spin w-5 h-5 text-primary-600" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
          </svg>
          <span class="text-sm text-gray-600 dark:text-gray-300">Seite wird verarbeitet...</span>
        </div>
      </div>

      <!-- Stats Overview -->
      <div class="card mb-6">
        <div class="flex items-center justify-between">
          <h3 class="font-semibold text-gray-900 dark:text-white">Überblick</h3>
          <div class="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
            <span>{{ activeCount }} von {{ items.length }} aktiv</span>
            <span v-if="progressStats.overallAccuracy">·  {{ progressStats.overallAccuracy }}% Genauigkeit</span>
            <span v-if="progressStats.masteredCount">· {{ progressStats.masteredCount }} beherrscht</span>
          </div>
        </div>
      </div>

      <!-- Vocabulary Table with selection -->
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-gray-900 dark:text-white">Vokabeln</h3>
          <div class="flex items-center gap-3">
            <button
              @click="selectAll"
              class="text-xs text-primary-600 hover:text-primary-700"
            >Alle auswählen</button>
            <button
              @click="deselectAll"
              class="text-xs text-gray-500 hover:text-gray-700"
            >Alle abwählen</button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left">
            <thead>
              <tr class="border-b border-gray-200 dark:border-gray-700">
                <th class="pb-3 w-10">
                  <input
                    type="checkbox"
                    :checked="allSelected"
                    @change="toggleAll"
                    class="rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-gray-600 dark:bg-gray-700"
                  />
                </th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400">#</th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400">Deutsch</th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400">{{ getLanguageName(vocabSet?.targetLanguage || 'fr') }}</th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400 text-center">Level</th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400 text-center hidden sm:table-cell">Richtig</th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400 hidden md:table-cell">Letzte Fehler</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, index) in items"
                :key="item.itemId"
                class="border-b border-gray-100 dark:border-gray-700"
                :class="{ 'opacity-40': !item.isActive }"
              >
                <td class="py-3">
                  <input
                    type="checkbox"
                    :checked="item.isActive"
                    @change="toggleItem(index)"
                    class="rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-gray-600 dark:bg-gray-700"
                  />
                </td>
                <td class="py-3 text-sm text-gray-400 dark:text-gray-500">{{ index + 1 }}</td>
                <td class="py-3 font-medium dark:text-gray-200">{{ item.source || item.german }}</td>
                <td class="py-3 dark:text-gray-300">{{ item.target || item.french }}</td>
                <td class="py-3 text-center">
                  <span v-if="getProgress(item.itemId)" class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="masteryClass(getProgress(item.itemId).masteryLevel)">
                    {{ getProgress(item.itemId).masteryLevel }}/5
                  </span>
                  <span v-else class="text-xs text-gray-300 dark:text-gray-600">—</span>
                </td>
                <td class="py-3 text-center text-sm hidden sm:table-cell">
                  <span v-if="getProgress(item.itemId)">
                    {{ getProgress(item.itemId).accuracy }}%
                  </span>
                  <span v-else class="text-gray-300 dark:text-gray-600">—</span>
                </td>
                <td class="py-3 text-xs text-gray-400 dark:text-gray-500 hidden md:table-cell">
                  <template v-if="getProgress(item.itemId)?.recentErrors?.length">
                    {{ getProgress(item.itemId).recentErrors.map(e => e.answer || e).join(', ') }}
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- Save button appears when selection changed -->
        <div v-if="selectionDirty" class="mt-4 flex justify-end">
          <button @click="saveSelection" class="btn-primary text-sm" :disabled="savingSelection">
            {{ savingSelection ? 'Speichern...' : 'Auswahl speichern' }}
          </button>
        </div>
      </div>
    </template>

    <div v-else class="card text-center py-12">
      <p class="text-gray-600 dark:text-gray-300">Vokabelset nicht gefunden.</p>
      <router-link to="/dashboard" class="btn-primary mt-4">Zum Dashboard</router-link>
    </div>

    <!-- Goal Modal -->
    <div v-if="showGoalModal" class="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center z-50 p-4" @click.self="showGoalModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full p-6">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">🎯 Lernziel erstellen</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Das Vokabelset wird zum Lernziel hinzugefügt.</p>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Titel</label>
            <input
              v-model="goalForm.title"
              type="text"
              placeholder="z.B. Vokabeltest Kapitel 3"
              class="input w-full"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Deadline</label>
            <input
              v-model="goalForm.deadline"
              type="date"
              :min="tomorrowDate"
              class="input w-full"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ziel-Level</label>
            <select v-model.number="goalForm.targetMastery" class="input w-full">
              <option :value="3">3 — Grundkenntnisse</option>
              <option :value="4">4 — Sicher</option>
              <option :value="5">5 — Perfekt</option>
            </select>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button @click="showGoalModal = false" class="btn-secondary">Abbrechen</button>
          <button
            @click="createGoal"
            class="btn-primary"
            :disabled="creatingGoal || !goalForm.title.trim() || !goalForm.deadline"
          >
            {{ creatingGoal ? 'Erstellt...' : 'Lernziel erstellen' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useVocabStore } from '@/stores/vocab'
import { useUpload } from '@/composables/useUpload'
import { useToast } from '@/composables/useToast'
import { getLanguageName } from '@/utils/languages'
import api from '@/services/api'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ImageDropzone from '@/components/upload/ImageDropzone.vue'

const props = defineProps({
  vocabSetId: { type: String, required: true }
})

const vocabStore = useVocabStore()
const upload = useUpload()
const { showSuccess, showError } = useToast()
const isLoading = ref(true)
const vocabSet = ref(null)
const items = ref([])
const showAddPage = ref(false)
const addingPage = ref(false)
const selectionDirty = ref(false)
const savingSelection = ref(false)
const progressMap = ref({})
const progressStats = ref({})

// Goal modal state
const showGoalModal = ref(false)
const creatingGoal = ref(false)
const goalForm = ref({
  title: '',
  deadline: '',
  targetMastery: 4
})

const tomorrowDate = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().split('T')[0]
})

const activeCount = computed(() => items.value.filter(i => i.isActive).length)
const allSelected = computed(() => items.value.length > 0 && items.value.every(i => i.isActive))

function toggleItem(index) {
  items.value[index].isActive = !items.value[index].isActive
  selectionDirty.value = true
}

function toggleAll() {
  const newState = !allSelected.value
  items.value.forEach(item => { item.isActive = newState })
  selectionDirty.value = true
}

function selectAll() {
  items.value.forEach(item => { item.isActive = true })
  selectionDirty.value = true
}

function deselectAll() {
  items.value.forEach(item => { item.isActive = false })
  selectionDirty.value = true
}

function getProgress(itemId) {
  return progressMap.value[itemId] || null
}

function masteryClass(level) {
  if (level <= 1) return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
  if (level === 2) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
  if (level === 3) return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
  return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
}

async function saveSelection() {
  savingSelection.value = true
  try {
    await api.put(`/vocab/${props.vocabSetId}`, {
      items: items.value
    })
    selectionDirty.value = false
    showSuccess('Auswahl gespeichert!')
  } catch (err) {
    showError('Fehler beim Speichern der Auswahl')
  } finally {
    savingSelection.value = false
  }
}

async function createGoal() {
  if (!goalForm.value.title.trim() || !goalForm.value.deadline) return
  creatingGoal.value = true
  try {
    await api.post('/goals', {
      title: goalForm.value.title.trim(),
      vocabSetIds: [props.vocabSetId],
      deadline: goalForm.value.deadline,
      targetMastery: goalForm.value.targetMastery
    })
    showSuccess('Lernziel erstellt!')
    showGoalModal.value = false
    goalForm.value = { title: '', deadline: '', targetMastery: 4 }
  } catch (err) {
    showError(err.response?.data?.error || 'Fehler beim Erstellen des Lernziels')
  } finally {
    creatingGoal.value = false
  }
}

onMounted(async () => {
  try {
    const data = await vocabStore.fetchVocabSet(props.vocabSetId)
    vocabSet.value = data
    items.value = data.items || []

    // Load progress data for this set
    try {
      const progRes = await api.get(`/progress/${props.vocabSetId}`)
      const progData = progRes.data
      progressStats.value = {
        overallAccuracy: progData.overallAccuracy,
        masteredCount: progData.masteredCount,
      }
      // Build lookup map by itemId
      for (const p of (progData.progress || [])) {
        progressMap.value[p.itemId] = p
      }
    } catch {
      // Progress not available yet — that's fine
    }
  } catch {
    // Error handled by store
  } finally {
    isLoading.value = false
  }
})

async function handleAddPage({ files, vocabSetId }) {
  addingPage.value = true
  try {
    // Upload files to existing set
    const { imageKeys } = await upload.uploadMultipleImages(files)

    // Trigger extraction for each
    for (const imageKey of imageKeys) {
      await upload.triggerExtraction(vocabSetId, imageKey)
      await upload.pollExtractionStatus(vocabSetId)
    }

    showSuccess(`${files.length} ${files.length === 1 ? 'Seite' : 'Seiten'} hinzugefügt!`)

    // Reload the set to show new items
    const data = await vocabStore.fetchVocabSet(props.vocabSetId)
    vocabSet.value = data
    items.value = data.items || []
    showAddPage.value = false
  } catch (err) {
    showError(err.message || 'Fehler beim Hinzufügen der Seite')
  } finally {
    addingPage.value = false
    upload.reset()
  }
}
</script>
