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
  // Async extraction progress (pages processed of total), for a live "X von Y".
  const pagesDone = ref(0)
  const pagesTotal = ref(0)
  const pagesFailed = ref(0)

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
   * Enqueue asynchronous extraction for a vocab set. The backend returns 202
   * immediately (202 Accepted) and processes each page via SQS in the
   * background; progress is tracked by polling. Passing no imageKey lets the
   * backend process ALL pages of the set.
   */
  async function triggerExtraction(vocabSetId) {
    extractionStatus.value = 'processing'
    try {
      const resp = await api.post('/vocab/process', { vocabSetId })
      pagesTotal.value = resp.data?.pagesTotal || 0
      pagesDone.value = 0
      pagesFailed.value = 0
      return vocabSetId
    } catch (err) {
      extractionStatus.value = 'failed'
      error.value = err.message || 'Extraktion fehlgeschlagen'
      throw err
    }
  }

  /**
   * Upload multiple files, then enqueue extraction ONCE for the whole set and
   * poll for progress. The heavy Textract+Bedrock work runs asynchronously in
   * the backend worker, so this no longer blocks on a synchronous request
   * (previously caused API Gateway 29s timeouts on multi-image uploads).
   * @param {File[]} files
   * @returns {{ vocabSetId }}
   */
  async function uploadAndExtractMultiple(files) {
    const { vocabSetId } = await uploadMultipleImages(files)

    // Enqueue extraction for the whole set (returns 202 immediately).
    await triggerExtraction(vocabSetId)
    // Poll until the backend finalises the set (review/failed).
    await pollExtractionStatus(vocabSetId)

    return { vocabSetId }
  }

  /**
   * Poll extraction status until the set is finalised (review/approved/failed).
   * Reads the async page counters so the UI can show live "X von Y" progress.
   * Uses a generous cap because async extraction of many pages can take a while.
   */
  async function pollExtractionStatus(vocabSetId, interval = 3000, maxAttempts = 200) {
    let attempts = 0

    return new Promise((resolve, reject) => {
      const poll = async () => {
        attempts++
        try {
          const response = await api.get(`/vocab/extraction/${vocabSetId}`)
          const data = response.data
          extractionStatus.value = data.status
          // Live progress counters (default 0 if backend omits them).
          pagesTotal.value = data.pagesTotal || pagesTotal.value || 0
          pagesDone.value = data.pagesDone || 0
          pagesFailed.value = data.pagesFailed || 0

          if (data.status === 'review' || data.status === 'approved') {
            resolve(data)
          } else if (data.status === 'failed') {
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
    pagesDone.value = 0
    pagesTotal.value = 0
    pagesFailed.value = 0
  }

  return {
    uploadProgress,
    isUploading,
    error,
    extractionStatus,
    filesProgress,
    pagesDone,
    pagesTotal,
    pagesFailed,
    uploadImage,
    uploadMultipleImages,
    uploadAndExtractMultiple,
    triggerExtraction,
    pollExtractionStatus,
    reset
  }
}
