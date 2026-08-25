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
          <span class="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">
            {{ activeCount }} von {{ items.length }} Vokabeln aktiv
          </span>
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
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">#</th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">Deutsch</th>
                <th class="pb-3 text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">Französisch</th>
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
                <td class="py-3 font-medium dark:text-gray-200">{{ item.german }}</td>
                <td class="py-3 dark:text-gray-300">{{ item.french }}</td>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useVocabStore } from '@/stores/vocab'
import { useUpload } from '@/composables/useUpload'
import { useToast } from '@/composables/useToast'
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

onMounted(async () => {
  try {
    const data = await vocabStore.fetchVocabSet(props.vocabSetId)
    vocabSet.value = data
    items.value = data.items || []
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
