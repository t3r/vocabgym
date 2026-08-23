<template>
  <div
    class="border-2 border-dashed rounded-lg p-8 text-center transition-colors"
    :class="dropzoneClasses"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
    @click="openFilePicker"
  >
    <!-- Preview -->
    <div v-if="preview" class="mb-4">
      <img :src="preview" alt="Vorschau" class="max-h-64 mx-auto rounded-lg shadow-md" />
      <button
        @click.stop="clearFile"
        class="mt-2 text-sm text-gray-500 hover:text-error"
      >
        Anderes Bild wählen
      </button>
    </div>

    <!-- Upload Prompt -->
    <div v-else>
      <svg class="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
      </svg>
      <p class="text-gray-600 mb-2">
        <span class="font-medium text-primary-600">Klicke hier</span> oder ziehe ein Bild hierher
      </p>
      <p class="text-xs text-gray-400">JPG, PNG oder HEIC · Max. 10 MB</p>
    </div>

    <!-- Hidden File Input -->
    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/heic"
      class="hidden"
      @change="handleFileSelect"
    />

    <!-- Upload Button (when file selected) -->
    <div v-if="selectedFile && !isUploading" class="mt-4">
      <button @click.stop="startUpload" class="btn-primary">
        Bild hochladen
      </button>
    </div>

    <!-- Validation Error -->
    <p v-if="validationError" class="mt-3 text-sm text-error">{{ validationError }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUpload } from '@/composables/useUpload'
import { isValidFileType, isValidFileSize } from '@/utils/validators'

const emit = defineEmits(['upload-success', 'upload-error'])

const { uploadImage, isUploading } = useUpload()

const fileInput = ref(null)
const selectedFile = ref(null)
const preview = ref(null)
const isDragging = ref(false)
const validationError = ref(null)

const dropzoneClasses = computed(() => ({
  'border-primary-400 bg-primary-50': isDragging.value,
  'border-gray-300 hover:border-primary-400 hover:bg-gray-50 cursor-pointer': !isDragging.value
}))

function openFilePicker() {
  if (!selectedFile.value) {
    fileInput.value?.click()
  }
}

function handleDragOver() {
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) validateAndSetFile(file)
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) validateAndSetFile(file)
}

function validateAndSetFile(file) {
  validationError.value = null

  const typeCheck = isValidFileType(file)
  if (typeCheck !== true) {
    validationError.value = typeCheck
    return
  }

  const sizeCheck = isValidFileSize(file)
  if (sizeCheck !== true) {
    validationError.value = sizeCheck
    return
  }

  selectedFile.value = file

  // Generate preview
  const reader = new FileReader()
  reader.onload = (e) => {
    preview.value = e.target.result
  }
  reader.readAsDataURL(file)
}

async function startUpload() {
  if (!selectedFile.value) return

  try {
    const result = await uploadImage(selectedFile.value)
    emit('upload-success', result)
  } catch (err) {
    emit('upload-error', err.message || 'Upload fehlgeschlagen')
  }
}

function clearFile() {
  selectedFile.value = null
  preview.value = null
  validationError.value = null
  if (fileInput.value) fileInput.value.value = ''
}
</script>
