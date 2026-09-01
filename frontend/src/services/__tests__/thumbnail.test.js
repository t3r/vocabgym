import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '@/services/api'
import { fetchThumbnail, _clearCache } from '@/services/thumbnail'

describe('thumbnail service — fetchThumbnail', () => {
  beforeEach(() => {
    _clearCache()
    api.get.mockReset()
    api.post.mockReset()
  })

  it('returns the URL immediately on a cache hit (no polling)', async () => {
    api.post.mockResolvedValueOnce({ data: { status: 'ready', url: 'https://s3/x.png' } })
    const url = await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1' })
    expect(url).toBe('https://s3/x.png')
    expect(api.get).not.toHaveBeenCalled()
  })

  it('polls until ready when the first response is pending', async () => {
    api.post.mockResolvedValueOnce({ data: { status: 'pending' } })
    api.get
      .mockResolvedValueOnce({ data: { status: 'pending' } })
      .mockResolvedValueOnce({ data: { status: 'ready', url: 'https://s3/y.png' } })

    const url = await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1', attempts: 3, intervalMs: 0 })
    expect(url).toBe('https://s3/y.png')
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('returns null when still pending after the poll budget', async () => {
    api.post.mockResolvedValueOnce({ data: { status: 'pending' } })
    api.get.mockResolvedValue({ data: { status: 'pending' } })
    const url = await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1', attempts: 2, intervalMs: 0 })
    expect(url).toBeNull()
  })

  it('returns null on error (e.g. 429 rate limit) without throwing', async () => {
    api.post.mockRejectedValueOnce({ response: { status: 429 } })
    const url = await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1', intervalMs: 0 })
    expect(url).toBeNull()
  })

  it('signals onPending(true) when generation is in progress', async () => {
    api.post.mockResolvedValueOnce({ data: { status: 'pending' } })
    api.get.mockResolvedValueOnce({ data: { status: 'ready', url: 'https://s3/p.png' } })
    const onPending = vi.fn()
    const url = await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1', attempts: 2, intervalMs: 0, onPending })
    expect(onPending).toHaveBeenCalledWith(true)
    expect(url).toBe('https://s3/p.png')
  })

  it('does not signal onPending on an immediate cache hit', async () => {
    api.post.mockResolvedValueOnce({ data: { status: 'ready', url: 'https://s3/h.png' } })
    const onPending = vi.fn()
    await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1', onPending })
    expect(onPending).not.toHaveBeenCalled()
  })

  it('caches the URL for the session (second call hits no API)', async () => {
    api.post.mockResolvedValueOnce({ data: { status: 'ready', url: 'https://s3/z.png' } })
    const first = await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1' })
    expect(first).toBe('https://s3/z.png')
    const second = await fetchThumbnail({ vocabSetId: 's1', itemId: 'i1' })
    expect(second).toBe('https://s3/z.png')
    expect(api.post).toHaveBeenCalledTimes(1)  // served from session cache
  })
})
