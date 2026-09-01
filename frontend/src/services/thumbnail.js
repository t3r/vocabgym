import api from '@/services/api'

/**
 * Thumbnail service — AI comic thumbnails for vocabulary items (via backend).
 *
 * The backend never accepts free text: a thumbnail is requested by
 * { vocabSetId, itemId } and the word to illustrate is resolved server-side
 * from the (owned or league-assigned) vocabulary item.
 *
 * Generation is async (SQS worker). Flow:
 *   POST /images/thumbnail          -> { status: 'ready', url } on a cache hit,
 *                                      or { status: 'pending' } (job enqueued)
 *   GET  /images/thumbnail/{s}/{i}  -> poll until { status: 'ready', url }
 *
 * A session cache of presigned URLs avoids re-requesting the same word during a
 * practice session (presigned URLs are valid ~1h).
 */

const _urlCache = new Map()

function _key(vocabSetId, itemId) {
  return `${vocabSetId}|${itemId}`
}

/** Request a thumbnail; returns { status, url? }. */
export async function requestThumbnail({ vocabSetId, itemId }) {
  const response = await api.post('/images/thumbnail', { vocabSetId, itemId })
  return response.data
}

/** Poll once for a thumbnail; returns { status, url? }. */
export async function pollThumbnail({ vocabSetId, itemId }) {
  const response = await api.get(`/images/thumbnail/${vocabSetId}/${itemId}`)
  return response.data
}

/**
 * Get a thumbnail URL, generating + polling if needed.
 *
 * Resolves to a presigned URL string, or null if unavailable (rate-limited,
 * error, or still pending after the poll budget — the UI then shows no image).
 *
 * @param {{vocabSetId, itemId, attempts?, intervalMs?}} opts
 */
export async function fetchThumbnail({ vocabSetId, itemId, attempts = 6, intervalMs = 2500 }) {
  const key = _key(vocabSetId, itemId)
  if (_urlCache.has(key)) {
    return _urlCache.get(key)
  }

  try {
    const first = await requestThumbnail({ vocabSetId, itemId })
    if (first.status === 'ready' && first.url) {
      _urlCache.set(key, first.url)
      return first.url
    }

    // Pending: poll a bounded number of times while the worker generates.
    for (let i = 0; i < attempts; i++) {
      await new Promise((r) => setTimeout(r, intervalMs))
      const res = await pollThumbnail({ vocabSetId, itemId })
      if (res.status === 'ready' && res.url) {
        _urlCache.set(key, res.url)
        return res.url
      }
    }
  } catch {
    // 429 (rate limit), 404, network, etc. → no thumbnail; UI falls back.
  }
  return null
}

/** Test helper: clear the session URL cache. */
export function _clearCache() {
  _urlCache.clear()
}
