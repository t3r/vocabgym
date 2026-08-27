<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header with title, cancel, save -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Vokabeln prüfen</h1>
        <p class="mt-1 text-gray-600 dark:text-gray-300">Überprüfe die extrahierten Vokabeln und korrigiere Fehler.</p>
      </div>
      <div class="flex gap-3">
        <button @click="handleCancel" class="btn-secondary">Abbrechen</button>
        <button @click="handleSave" class="btn-primary" :disabled="isSaving">
          {{ isSaving ? 'Speichern...' : 'Speichern & Freigeben' }}
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="isLoading" class="py-12" />

    <div v-else class="space-y-6">
      <!-- Metadata Form -->
      <MetadataForm
        v-model:title="metadata.title"
        v-model:chapter="metadata.chapter"
        v-model:page-number="metadata.pageNumber"
        v-model:topic="metadata.topic"
      />

      <!-- Language Selector -->
      <div class="card flex items-center gap-4">
        <label class="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">Zielsprache:</label>
        <select v-model="selectedLanguage" class="input flex-1 max-w-xs" @change="handleLanguageChange">
          <option v-for="lang in SUPPORTED_LANGUAGES" :key="lang.code" :value="lang.code">
            {{ lang.flag }} {{ lang.name }}
          </option>
        </select>
      </div>

      <!-- Image groups -->
      <div v-for="(group, groupIndex) in imageGroups" :key="group.imageKey" class="card">
        <!-- Image -->
        <div v-if="group.imageUrl" class="mb-4 rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
          <img
            :src="group.imageUrl"
            :alt="`Seite ${groupIndex + 1}`"
            class="max-h-96 w-full object-contain bg-gray-50 dark:bg-gray-800"
            loading="lazy"
          />
        </div>

        <h3 class="font-semibold text-gray-900 dark:text-white mb-3">Seite {{ groupIndex + 1 }}</h3>

        <!-- Editable table for this image's items -->
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-gray-200 dark:border-gray-700">
                <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400 w-8">#</th>
                <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400">Deutsch</th>
                <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400">{{ targetLanguageName }}</th>
                <th class="pb-2 w-10"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, itemIndex) in group.items"
                :key="item.itemId"
                class="border-b border-gray-100 dark:border-gray-700/50 group"
              >
                <td class="py-2 text-sm text-gray-400 dark:text-gray-500 align-middle">{{ itemIndex + 1 }}</td>
                <td class="py-2 pr-2">
                  <input
                    :value="item.source || item.german"
                    @input="updateItem(item, 'source', $event.target.value)"
                    class="input-field text-sm"
                    :class="{ 'border-error': !(item.source || item.german)?.trim() }"
                    placeholder="Deutsch"
                  />
                </td>
                <td class="py-2 pr-2">
                  <input
                    :value="item.target || item.french"
                    @input="updateItem(item, 'target', $event.target.value)"
                    class="input-field text-sm"
                    :class="{ 'border-error': !(item.target || item.french)?.trim() }"
                    :placeholder="targetLanguageName"
                  />
                </td>
                <td class="py-2 text-center">
                  <button
                    @click="deleteItem(item)"
                    class="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 dark:text-red-500 dark:hover:text-red-400 transition-all p-1 rounded"
                    aria-label="Zeile löschen"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Add row button -->
        <button
          @click="addItem(group.imageKey)"
          class="mt-4 w-full py-2 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-500 dark:text-gray-400 hover:border-primary-400 hover:text-primary-600 dark:hover:border-primary-500 dark:hover:text-primary-400 transition-colors"
        >
          + Eintrag hinzufügen
        </button>
      </div>

      <!-- Unassigned items (no imageKey) -->
      <div v-if="unassignedItems.length > 0" class="card">
        <h3 class="font-semibold text-gray-900 dark:text-white mb-3">Weitere Vokabeln</h3>

        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-gray-200 dark:border-gray-700">
                <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400 w-8">#</th>
                <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400">Deutsch</th>
                <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400">{{ targetLanguageName }}</th>
                <th class="pb-2 w-10"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, itemIndex) in unassignedItems"
                :key="item.itemId"
                class="border-b border-gray-100 dark:border-gray-700/50 group"
              >
                <td class="py-2 text-sm text-gray-400 dark:text-gray-500 align-middle">{{ itemIndex + 1 }}</td>
                <td class="py-2 pr-2">
                  <input
                    :value="item.source || item.german"
                    @input="updateItem(item, 'source', $event.target.value)"
                    class="input-field text-sm"
                    :class="{ 'border-error': !(item.source || item.german)?.trim() }"
                    placeholder="Deutsch"
                  />
                </td>
                <td class="py-2 pr-2">
                  <input
                    :value="item.target || item.french"
                    @input="updateItem(item, 'target', $event.target.value)"
                    class="input-field text-sm"
                    :class="{ 'border-error': !(item.target || item.french)?.trim() }"
                    :placeholder="targetLanguageName"
                  />
                </td>
                <td class="py-2 text-center">
                  <button
                    @click="deleteItem(item)"
                    class="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 dark:text-red-500 dark:hover:text-red-400 transition-all p-1 rounded"
                    aria-label="Zeile löschen"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <button
          @click="addItem(null)"
          class="mt-4 w-full py-2 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-500 dark:text-gray-400 hover:border-primary-400 hover:text-primary-600 dark:hover:border-primary-500 dark:hover:text-primary-400 transition-colors"
        >
          + Eintrag hinzufügen
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVocabStore } from '@/stores/vocab'
import { useToast } from '@/composables/useToast'
import { getLanguageName, SUPPORTED_LANGUAGES } from '@/utils/languages'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import MetadataForm from '@/components/review/MetadataForm.vue'

const props = defineProps({
  vocabSetId: { type: String, required: true }
})

const router = useRouter()
const vocabStore = useVocabStore()
const { showSuccess, showError } = useToast()

const isLoading = ref(true)
const isSaving = ref(false)
const vocabSet = ref(null)
const items = ref([])
const selectedLanguage = ref('fr')
const metadata = reactive({
  title: '',
  chapter: '',
  pageNumber: '',
  topic: ''
})

const targetLanguageName = computed(() => {
  return getLanguageName(selectedLanguage.value || 'fr')
})

/**
 * Group items by their imageKey, matching against vocabSet.imageKeys/imageUrls.
 */
const imageGroups = computed(() => {
  const imageKeys = vocabSet.value?.imageKeys || []
  const imageUrls = vocabSet.value?.imageUrls || []

  // Build a map of imageKey -> imageUrl
  const keyToUrl = {}
  imageKeys.forEach((key, idx) => {
    keyToUrl[key] = imageUrls[idx] || null
  })

  // If no imageKeys but we have a legacy sourceImageKey/sourceImageUrl, use that
  if (imageKeys.length === 0 && vocabSet.value?.sourceImageKey) {
    const legacyKey = vocabSet.value.sourceImageKey
    keyToUrl[legacyKey] = vocabSet.value.sourceImageUrl || null
    imageKeys.push(legacyKey)
  }

  // Group items by imageKey
  const groups = []
  const usedKeys = new Set()

  for (const key of imageKeys) {
    const groupItems = items.value.filter(item => item.imageKey === key)
    if (groupItems.length > 0 || imageUrls.length > 0) {
      groups.push({
        imageKey: key,
        imageUrl: keyToUrl[key] || null,
        items: groupItems
      })
      usedKeys.add(key)
    }
  }

  // Also show image cards that have no items yet (newly uploaded images)
  for (const key of imageKeys) {
    if (!usedKeys.has(key)) {
      groups.push({
        imageKey: key,
        imageUrl: keyToUrl[key] || null,
        items: []
      })
    }
  }

  return groups
})

/**
 * Items without an imageKey (legacy data or manually added without assignment).
 */
const unassignedItems = computed(() => {
  const imageKeys = vocabSet.value?.imageKeys || []
  const legacyKey = vocabSet.value?.sourceImageKey
  const allKnownKeys = new Set([...imageKeys])
  if (legacyKey) allKnownKeys.add(legacyKey)

  return items.value.filter(item => !item.imageKey || !allKnownKeys.has(item.imageKey))
})

onMounted(async () => {
  try {
    const data = await vocabStore.fetchVocabSet(props.vocabSetId)
    vocabSet.value = data
    items.value = data.items || []
    selectedLanguage.value = data.targetLanguage || 'fr'
    metadata.title = data.title || ''
    metadata.chapter = data.metadata?.chapter || ''
    metadata.pageNumber = data.metadata?.pageNumber || ''
    metadata.topic = data.metadata?.topic || ''
  } catch {
    showError('Fehler beim Laden des Vokabelsets')
  } finally {
    isLoading.value = false
  }
})

function updateItem(item, field, value) {
  const idx = items.value.indexOf(item)
  if (idx !== -1) {
    items.value[idx] = { ...items.value[idx], [field]: value }
  }
}

function deleteItem(item) {
  const idx = items.value.indexOf(item)
  if (idx !== -1) {
    items.value.splice(idx, 1)
  }
}

function addItem(imageKey) {
  const newItem = {
    itemId: `new-${Date.now()}`,
    source: '',
    target: '',
    notes: '',
    order: items.value.length + 1
  }
  if (imageKey) {
    newItem.imageKey = imageKey
  }
  items.value.push(newItem)
}

async function handleSave() {
  // Validate: no empty pairs
  const invalidItems = items.value.filter(
    (item) => !(item.source || item.german)?.trim() || !(item.target || item.french)?.trim()
  )
  if (invalidItems.length > 0) {
    showError('Bitte fülle alle Quell- und Zielsprachfelder aus.')
    return
  }

  isSaving.value = true
  try {
    await vocabStore.updateVocabSet(props.vocabSetId, {
      title: metadata.title || 'Unbenanntes Set',
      targetLanguage: selectedLanguage.value,
      metadata: {
        chapter: metadata.chapter,
        pageNumber: metadata.pageNumber ? Number(metadata.pageNumber) : null,
        topic: metadata.topic
      },
      items: items.value
    })
    showSuccess('Vokabelset gespeichert!')
    router.push({ name: 'Dashboard' })
  } catch {
    showError('Fehler beim Speichern')
  } finally {
    isSaving.value = false
  }
}

function handleLanguageChange() {
  // Language change is reflected immediately in column headers via targetLanguageName computed.
  // The new value is saved when user clicks "Speichern & Freigeben".
}

function handleCancel() {
  router.push({ name: 'Dashboard' })
}
</script>
