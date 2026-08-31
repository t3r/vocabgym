<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Arbeitsbuchseiten hochladen</h1>
      <p class="mt-1 text-gray-600 dark:text-gray-400 dark:text-gray-500">
        Fotografiere eine oder mehrere Vokabeltabellen und lade die Bilder hier hoch.
      </p>
    </div>

    <!-- Upload Phase -->
    <div v-if="phase === 'select'" class="card">
      <!-- Language Selector -->
      <div class="mb-6">
        <label for="target-language" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Zielsprache:</label>
        <select
          id="target-language"
          v-model="targetLanguage"
          class="input-field"
        >
          <option value="">🔍 Automatisch erkennen</option>
          <option v-for="lang in SUPPORTED_LANGUAGES" :key="lang.code" :value="lang.code">
            {{ lang.flag }} {{ lang.name }}
          </option>
        </select>
      </div>

      <ImageDropzone
        @upload-success="handleStartUpload"
        @upload-error="handleUploadError"
      />
    </div>

    <!-- Processing Phase -->
    <div v-else-if="phase === 'processing'" class="card">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Verarbeite {{ totalFiles }} {{ totalFiles === 1 ? 'Bild' : 'Bilder' }}...
      </h2>

      <!-- Per-file progress -->
      <div class="space-y-3">
        <div v-for="(fp, i) in upload.filesProgress.value" :key="i" class="flex items-center gap-3">
          <span class="text-sm text-gray-600 dark:text-gray-300 truncate w-40">{{ fp.name }}</span>
          <div class="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              class="h-2 rounded-full transition-all duration-300"
              :class="fp.status === 'error' ? 'bg-error' : 'bg-primary-500'"
              :style="{ width: `${fp.progress}%` }"
            ></div>
          </div>
          <span class="text-xs w-16 text-right">
            <span v-if="fp.status === 'done'" class="text-success">✓</span>
            <span v-else-if="fp.status === 'error'" class="text-error">✗</span>
            <span v-else-if="fp.status === 'uploading'" class="text-primary-600">{{ upload.uploadProgress.value }}%</span>
            <span v-else class="text-gray-400 dark:text-gray-500">Warten...</span>
          </span>
        </div>
      </div>

      <!-- Extraction status -->
      <div v-if="extractionPhase" class="mt-6 flex items-center gap-3">
        <svg class="animate-spin w-5 h-5 text-primary-600" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
        </svg>
        <span class="text-sm text-gray-600 dark:text-gray-300">
          <template v-if="upload.pagesTotal.value > 0">
            Vokabeln werden extrahiert... Seite {{ upload.pagesDone.value + upload.pagesFailed.value }} von {{ upload.pagesTotal.value }}
          </template>
          <template v-else>
            Vokabeln werden extrahiert...
          </template>
        </span>
      </div>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
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
import { SUPPORTED_LANGUAGES, DEFAULT_TARGET_LANGUAGE } from '@/utils/languages'
import ImageDropzone from '@/components/upload/ImageDropzone.vue'

const router = useRouter()
const upload = useUpload()
const { showSuccess, showError } = useToast()

const phase = ref('select') // 'select' | 'processing'
const error = ref(null)
const totalFiles = ref(0)
const extractionPhase = ref(false)
const targetLanguage = ref('')

async function handleStartUpload({ files, vocabSetId }) {
  phase.value = 'processing'
  totalFiles.value = files.length
  error.value = null
  extractionPhase.value = false

  try {
    // Upload all files (first creates set, rest add to it)
    const { vocabSetId: setId } = await upload.uploadMultipleImages(files, targetLanguage.value)

    // Enqueue extraction for the whole set (returns 202 immediately) and poll
    // for live progress. The heavy work runs asynchronously in the backend.
    extractionPhase.value = true
    await upload.triggerExtraction(setId)
    await upload.pollExtractionStatus(setId)

    const failed = upload.pagesFailed.value
    if (failed > 0) {
      showSuccess(`${files.length} Seiten verarbeitet (${failed} mit Fehler — bitte prüfen).`)
    } else {
      showSuccess(`${files.length} ${files.length === 1 ? 'Seite' : 'Seiten'} erfolgreich verarbeitet!`)
    }
    router.push({ name: 'Review', params: { vocabSetId: setId } })
  } catch (err) {
    error.value = err.message
    showError(err.message || 'Verarbeitung fehlgeschlagen')
  }
}

function handleUploadError(message) {
  error.value = message
  showError(message)
}

function reset() {
  phase.value = 'select'
  error.value = null
  totalFiles.value = 0
  extractionPhase.value = false
  upload.reset()
}
</script>
