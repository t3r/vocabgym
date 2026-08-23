import { ref } from 'vue'
import api from '@/services/api'

/**
 * Composable for handling image upload with S3 presigned URLs.
 */
export function useUpload() {
  const uploadProgress = ref(0)
  const isUploading = ref(false)
  const error = ref(null)
  const extractionStatus = ref(null)

  /**
   * Upload an image file to S3 via presigned URL
   * Returns the vocabSetId and imageKey
   */
  async function uploadImage(file) {
    isUploading.value = true
    uploadProgress.value = 0
    error.value = null

    try {
      // Step 1: Request presigned URL from backend
      const presignResponse = await api.post('/vocab/upload', {
        fileName: file.name,
        contentType: file.type
      })

      const { uploadUrl, vocabSetId, imageKey } = presignResponse.data

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
      return { vocabSetId, imageKey }
    } catch (err) {
      error.value = err.message || 'Upload fehlgeschlagen'
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
  }

  return {
    uploadProgress,
    isUploading,
    error,
    extractionStatus,
    uploadImage,
    triggerExtraction,
    pollExtractionStatus,
    reset
  }
}
