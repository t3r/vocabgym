<template>
  <!-- Review view: Image preview + editable vocabulary table -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Left: Image Preview -->
      <div class="card">
        <ImagePreview :image-url="vocabSet?.sourceImageUrl" />
      </div>

      <!-- Right: Editable Table + Metadata -->
      <div class="space-y-6">
        <MetadataForm
          v-model:title="metadata.title"
          v-model:chapter="metadata.chapter"
          v-model:page-number="metadata.pageNumber"
          v-model:topic="metadata.topic"
        />

        <VocabTable
          :items="items"
          :target-language="vocabSet?.targetLanguage || 'fr'"
          @update="handleItemUpdate"
          @delete="handleItemDelete"
          @add="handleItemAdd"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVocabStore } from '@/stores/vocab'
import { useToast } from '@/composables/useToast'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ImagePreview from '@/components/review/ImagePreview.vue'
import MetadataForm from '@/components/review/MetadataForm.vue'
import VocabTable from '@/components/review/VocabTable.vue'

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
const metadata = reactive({
  title: '',
  chapter: '',
  pageNumber: '',
  topic: ''
})

onMounted(async () => {
  try {
    const data = await vocabStore.fetchVocabSet(props.vocabSetId)
    vocabSet.value = data
    items.value = data.items || []
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

function handleItemUpdate(index, field, value) {
  items.value[index] = { ...items.value[index], [field]: value }
}

function handleItemDelete(index) {
  items.value.splice(index, 1)
}

function handleItemAdd() {
  items.value.push({
    itemId: `new-${Date.now()}`,
    source: '',
    target: '',
    notes: '',
    order: items.value.length + 1
  })
}

async function handleSave() {
  // Validate: no empty pairs
  const invalidItems = items.value.filter((item) => !(item.source || item.german)?.trim() || !(item.target || item.french)?.trim())
  if (invalidItems.length > 0) {
    showError('Bitte fülle alle Quell- und Zielsprachfelder aus.')
    return
  }

  isSaving.value = true
  try {
    await vocabStore.updateVocabSet(props.vocabSetId, {
      title: metadata.title || 'Unbenanntes Set',
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

function handleCancel() {
  router.push({ name: 'Dashboard' })
}
</script>
