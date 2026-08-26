import { ref } from 'vue'
import api from '@/services/api'

/**
 * Composable for handling image upload with S3 presigned URLs.
 * Supports multiple files and adding pages to existing sets.
 */
export function useUpload() {
  const uploadProgress = ref(0)
  const isUploading = ref(false)
  const error = ref(null)
  const extractionStatus = ref(null)
  const filesProgress = ref([]) // Per-file progress for multi-upload

  /**
   * Upload a single image file to S3 via presigned URL.
   * @param {File} file - The file to upload
   * @param {string|null} vocabSetId - Optional existing set ID to add to
   * @param {string|null} targetLanguage - Target language code (e.g. 'fr', 'en', 'es', 'it')
   * @returns {{ vocabSetId, imageKey }}
   */
  async function uploadImage(file, vocabSetId = null, targetLanguage = null) {
    isUploading.value = true
    uploadProgress.value = 0
    error.value = null

    try {
      // Step 1: Request presigned URL from backend
      const payload = {
        fileName: file.name,
        contentType: file.type || 'image/jpeg'
      }
      if (vocabSetId) {
        payload.vocabSetId = vocabSetId
      }
      if (targetLanguage) {
        payload.targetLanguage = targetLanguage
      }

      const presignResponse = await api.post('/vocab/upload', payload)
      const { uploadUrl, vocabSetId: returnedId, imageKey } = presignResponse.data

      // Step 2: Upload file directly to S3
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('PUT', uploadUrl)

        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) {
            uploadProgress.value = Math.round((event.loaded / event.total) * 100)
          }
        })

        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve()
          } else {
            reject(new Error(`Upload failed with status ${xhr.status}`))
          }
        })

        xhr.addEventListener('error', () => reject(new Error('Upload failed')))
        xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')))

        xhr.send(file)
      })

      uploadProgress.value = 100
      return { vocabSetId: returnedId, imageKey }
    } catch (err) {
      error.value = err.message || 'Upload fehlgeschlagen'
      throw err
    } finally {
      isUploading.value = false
    }
  }

  /**
   * Upload multiple files, creating one vocab set and adding all pages to it.
   * First file creates the set, subsequent files add to it.
   * @param {File[]} files - Array of files to upload
   * @param {string|null} targetLanguage - Target language code
   * @returns {{ vocabSetId, imageKeys: string[] }}
   */
  async function uploadMultipleImages(files, targetLanguage = null) {
    isUploading.value = true
    error.value = null
    filesProgress.value = files.map((f) => ({ name: f.name, progress: 0, status: 'pending' }))

    let vocabSetId = null
    const imageKeys = []

    try {
      for (let i = 0; i < files.length; i++) {
        filesProgress.value[i].status = 'uploading'

        const result = await uploadImage(files[i], vocabSetId, targetLanguage)

        // First file creates the set, subsequent files reuse the ID
        if (!vocabSetId) {
          vocabSetId = result.vocabSetId
        }

        imageKeys.push(result.imageKey)
        filesProgress.value[i].progress = 100
        filesProgress.value[i].status = 'done'
      }

      return { vocabSetId, imageKeys }
    } catch (err) {
      const failedIndex = filesProgress.value.findIndex((f) => f.status === 'uploading')
      if (failedIndex >= 0) {
        filesProgress.value[failedIndex].status = 'error'
      }
      throw err
    } finally {
      isUploading.value = false
    }
  }

  /**
   * Trigger extraction on uploaded image
   */
  async function triggerExtraction(vocabSetId, imageKey) {
    extractionStatus.value = 'processing'
    try {
      await api.post('/vocab/process', { vocabSetId, imageKey })
      return vocabSetId
    } catch (err) {
      extractionStatus.value = 'failed'
      error.value = err.message || 'Extraktion fehlgeschlagen'
      throw err
    }
  }

  /**
   * Upload multiple files and trigger extraction for each sequentially.
   * @param {File[]} files
   * @returns {{ vocabSetId }}
   */
  async function uploadAndExtractMultiple(files) {
    const { vocabSetId, imageKeys } = await uploadMultipleImages(files)

    // Trigger extraction for each image
    extractionStatus.value = 'processing'
    for (const imageKey of imageKeys) {
      await triggerExtraction(vocabSetId, imageKey)
      await pollExtractionStatus(vocabSetId)
    }

    return { vocabSetId }
  }

  /**
   * Poll extraction status until complete or failed
   */
  async function pollExtractionStatus(vocabSetId, interval = 2000, maxAttempts = 30) {
    let attempts = 0

    return new Promise((resolve, reject) => {
      const poll = async () => {
        attempts++
        try {
          const response = await api.get(`/vocab/extraction/${vocabSetId}`)
          extractionStatus.value = response.data.status

          if (response.data.status === 'review' || response.data.status === 'approved') {
            resolve(response.data)
          } else if (response.data.status === 'failed') {
            reject(new Error('Extraktion fehlgeschlagen'))
          } else if (attempts >= maxAttempts) {
            reject(new Error('Zeitüberschreitung bei der Extraktion'))
          } else {
            setTimeout(poll, interval)
          }
        } catch (err) {
          if (attempts >= maxAttempts) {
            reject(err)
          } else {
            setTimeout(poll, interval)
          }
        }
      }

      poll()
    })
  }

  function reset() {
    uploadProgress.value = 0
    isUploading.value = false
    error.value = null
    extractionStatus.value = null
    filesProgress.value = []
  }

  return {
    uploadProgress,
    isUploading,
    error,
    extractionStatus,
    filesProgress,
    uploadImage,
    uploadMultipleImages,
    uploadAndExtractMultiple,
    triggerExtraction,
    pollExtractionStatus,
    reset
  }
}
