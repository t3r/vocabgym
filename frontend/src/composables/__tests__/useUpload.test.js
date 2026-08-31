import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the api service used by the composable.
vi.mock('@/services/api', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

import api from '@/services/api'
import { useUpload } from '@/composables/useUpload'

describe('useUpload async extraction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('triggerExtraction enqueues once for the whole set (no imageKey) and stores pagesTotal', async () => {
    api.post.mockResolvedValueOnce({ data: { vocabSetId: 'vs1', status: 'processing', pagesTotal: 3 } })
    const u = useUpload()
    await u.triggerExtraction('vs1')

    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/vocab/process', { vocabSetId: 'vs1' })
    expect(u.pagesTotal.value).toBe(3)
    expect(u.extractionStatus.value).toBe('processing')
  })

  it('pollExtractionStatus reads counters and resolves on review', async () => {
    // First poll: still processing 1/3; second poll: review 3/3.
    api.get
      .mockResolvedValueOnce({ data: { status: 'processing', pagesTotal: 3, pagesDone: 1, pagesFailed: 0 } })
      .mockResolvedValueOnce({ data: { status: 'review', pagesTotal: 3, pagesDone: 3, pagesFailed: 0 } })

    const u = useUpload()
    const result = await u.pollExtractionStatus('vs1', 1, 10) // tiny interval for the test

    expect(result.status).toBe('review')
    expect(u.pagesDone.value).toBe(3)
    expect(u.pagesTotal.value).toBe(3)
    expect(api.get).toHaveBeenCalledWith('/vocab/extraction/vs1')
  })

  it('pollExtractionStatus rejects on failed status', async () => {
    api.get.mockResolvedValueOnce({ data: { status: 'failed', pagesTotal: 2, pagesDone: 0, pagesFailed: 2 } })
    const u = useUpload()
    await expect(u.pollExtractionStatus('vs1', 1, 10)).rejects.toThrow()
    expect(u.pagesFailed.value).toBe(2)
  })
})
