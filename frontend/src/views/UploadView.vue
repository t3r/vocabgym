<template>
  <!-- Upload view: Image dropzone, upload progress, extraction status -->
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-900">Arbeitsbuchseite hochladen</h1>
      <p class="mt-1 text-gray-600">
        Fotografiere die Vokabeltabelle und lade das Bild hier hoch.
      </p>
    </div>

    <!-- Upload Phase -->
    <div v-if="!vocabSetId" class="card">
      <ImageDropzone
        @upload-success="handleUploadSuccess"
        @upload-error="handleUploadError"
      />
      <UploadProgress
        v-if="upload.isUploading.value"
        :progress="upload.uploadProgress.value"
      />
    </div>

    <!-- Extraction Phase -->
    <div v-else class="card">
      <ExtractionStatus
        :status="upload.extractionStatus.value"
        :vocab-set-id="vocabSetId"
        @complete="handleExtractionComplete"
        @error="handleExtractionError"
      />
    </div>

    <!-- Error Display -->
    <div v-if="error" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
      <p class="text-error text-sm">{{ error }}</p>
      <button @click="reset" class="mt-2 text-sm text-primary-600 hover:text-primary-700">
        Erneut versuchen
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUpload } from '@/composables/useUpload'
import { useToast } from '@/composables/useToast'
import ImageDropzone from '@/components/upload/ImageDropzone.vue'
import UploadProgress from '@/components/upload/UploadProgress.vue'
import ExtractionStatus from '@/components/upload/ExtractionStatus.vue'

const router = useRouter()
const upload = useUpload()
const { showSuccess, showError } = useToast()

const vocabSetId = ref(null)
const error = ref(null)

async function handleUploadSuccess({ vocabSetId: id, imageKey }) {
  vocabSetId.value = id
  error.value = null

  try {
    await upload.triggerExtraction(id, imageKey)
    const result = await upload.pollExtractionStatus(id)

    if (result.status === 'review') {
      showSuccess('Vokabeln wurden erfolgreich extrahiert!')
      router.push({ name: 'Review', params: { vocabSetId: id } })
    }
  } catch (err) {
    error.value = err.message
  }
}

function handleUploadError(message) {
  error.value = message
  showError(message)
}

function handleExtractionComplete(result) {
  showSuccess('Extraktion abgeschlossen!')
  router.push({ name: 'Review', params: { vocabSetId: vocabSetId.value } })
}

function handleExtractionError(message) {
  error.value = message
}

function reset() {
  vocabSetId.value = null
  error.value = null
  upload.reset()
}
</script>
