<template>
  <div
    class="border-2 border-dashed rounded-lg p-8 text-center transition-colors"
    :class="dropzoneClasses"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
    @click="openFilePicker"
  >
    <!-- Previews -->
    <div v-if="selectedFiles.length > 0" class="mb-4">
      <div class="flex flex-wrap gap-3 justify-center">
        <div v-for="(file, i) in selectedFiles" :key="i" class="relative">
          <img :src="previews[i]" alt="Vorschau" class="w-24 h-24 object-cover rounded-lg shadow-md" />
          <button
            @click.stop="removeFile(i)"
            class="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center hover:bg-red-600"
          >✕</button>
        </div>
      </div>
      <button
        @click.stop="openFilePicker"
        class="mt-3 text-sm text-primary-600 hover:text-primary-700"
      >
        + Weitere Bilder hinzufügen
      </button>
    </div>

    <!-- Upload Prompt -->
    <div v-else>
      <svg class="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
      </svg>
      <p class="text-gray-600 dark:text-gray-300 mb-2">
        <span class="font-medium text-primary-600">Klicke hier</span> oder ziehe Bilder hierher
      </p>
      <p class="text-xs text-gray-400 dark:text-gray-500">JPG, PNG oder HEIC · Max. 10 MB pro Bild · Mehrere Seiten möglich</p>
    </div>

    <!-- Hidden File Input -->
    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/heic"
      multiple
      class="hidden"
      @change="handleFileSelect"
    />

    <!-- Upload Button (when files selected) -->
    <div v-if="selectedFiles.length > 0 && !isUploading" class="mt-4">
      <button @click.stop="startUpload" class="btn-primary">
        {{ selectedFiles.length === 1 ? 'Bild hochladen' : `${selectedFiles.length} Bilder hochladen` }}
      </button>
    </div>

    <!-- Validation Error -->
    <p v-if="validationError" class="mt-3 text-sm text-error">{{ validationError }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { isValidFileType, isValidFileSize } from '@/utils/validators'

const props = defineProps({
  vocabSetId: { type: String, default: null }
})

const emit = defineEmits(['files-selected', 'upload-success', 'upload-error'])

const fileInput = ref(null)
const selectedFiles = ref([])
const previews = ref([])
const isDragging = ref(false)
const validationError = ref(null)
const isUploading = ref(false)

const dropzoneClasses = computed(() => ({
  'border-primary-400 bg-primary-50 dark:bg-primary-900/20': isDragging.value,
  'border-gray-300 hover:border-primary-400 hover:bg-gray-50 dark:hover:bg-gray-800 dark:border-gray-600 dark:hover:border-primary-400 dark:hover:bg-gray-800 cursor-pointer': !isDragging.value
}))

function openFilePicker() {
  fileInput.value?.click()
}

function handleDragOver() {
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(event) {
  isDragging.value = false
  const files = Array.from(event.dataTransfer.files)
  addFiles(files)
}

function handleFileSelect(event) {
  const files = Array.from(event.target.files)
  addFiles(files)
  // Reset input so same file can be re-selected
  if (fileInput.value) fileInput.value.value = ''
}

function addFiles(files) {
  validationError.value = null

  for (const file of files) {
    const typeCheck = isValidFileType(file)
    if (typeCheck !== true) {
      validationError.value = `${file.name}: ${typeCheck}`
      continue
    }

    const sizeCheck = isValidFileSize(file)
    if (sizeCheck !== true) {
      validationError.value = `${file.name}: ${sizeCheck}`
      continue
    }

    selectedFiles.value.push(file)

    // Generate preview
    const reader = new FileReader()
    reader.onload = (e) => {
      previews.value.push(e.target.result)
    }
    reader.readAsDataURL(file)
  }

  emit('files-selected', selectedFiles.value)
}

function removeFile(index) {
  selectedFiles.value.splice(index, 1)
  previews.value.splice(index, 1)
  emit('files-selected', selectedFiles.value)
}

function startUpload() {
  if (selectedFiles.value.length === 0) return
  isUploading.value = true
  emit('upload-success', { files: selectedFiles.value, vocabSetId: props.vocabSetId })
}

function clearAll() {
  selectedFiles.value = []
  previews.value = []
  validationError.value = null
  isUploading.value = false
  if (fileInput.value) fileInput.value.value = ''
}

defineExpose({ clearAll })
</script>
