import api from '@/services/api'

/**
 * Text-to-Speech service (Amazon Polly via backend).
 *
 * The backend never accepts free text: synthesis is requested by
 * { vocabSetId, itemId, voiceId } and the word to speak is resolved
 * server-side from the (owned) vocabulary item.
 */

// Session cache of presigned audio URLs, keyed by vocabSetId|itemId|voiceId.
// Presigned URLs are valid ~1h; caching avoids duplicate requests within a session.
const _urlCache = new Map()

function _cacheKey({ vocabSetId, itemId, voiceId }) {
  return `${vocabSetId}|${itemId}|${voiceId}`
}

/**
 * Fetch available standard-engine voices for a language, grouped by accent.
 * @param {string} lang - target language code (fr|en|es|it)
 * @returns {Promise<{lang: string, accents: Array}>}
 */
export async function getVoices(lang) {
  const response = await api.get('/tts/voices', { params: { lang } })
  return response.data
}

/**
 * Request synthesis of a vocab item's target word in the given voice.
 * @param {{vocabSetId: string, itemId: string, voiceId: string}} req
 * @returns {Promise<string>} presigned audio URL
 */
export async function synthesize({ vocabSetId, itemId, voiceId }) {
  const key = _cacheKey({ vocabSetId, itemId, voiceId })
  if (_urlCache.has(key)) {
    return _urlCache.get(key)
  }

  const response = await api.post('/tts/synthesize', { vocabSetId, itemId, voiceId })
  const audioUrl = response.data?.audioUrl
  if (audioUrl) {
    _urlCache.set(key, audioUrl)
  }
  return audioUrl
}

/**
 * Play an audio URL. Resolves when playback starts (or throws on failure).
 * @param {string} url
 * @returns {Promise<HTMLAudioElement>}
 */
export async function playAudio(url) {
  const audio = new Audio(url)
  await audio.play()
  return audio
}

/**
 * Convenience: synthesize the item's word and play it.
 * @param {{vocabSetId: string, itemId: string, voiceId: string}} req
 */
export async function pronounce(req) {
  const url = await synthesize(req)
  if (!url) {
    throw new Error('Keine Audio-URL erhalten')
  }
  return playAudio(url)
}

/** Clear the in-memory URL cache (e.g. for tests). */
export function _clearCache() {
  _urlCache.clear()
}

/**
 * Resolve the voice to use for a language: the one stored in localStorage,
 * otherwise the first voice of the first accent returned by the backend.
 * @param {string} lang
 * @returns {Promise<string|null>} voiceId or null if none available
 */
export async function resolveVoiceId(lang) {
  try {
    const raw = localStorage.getItem(`vocabgym_tts_${lang}`)
    if (raw) {
      const stored = JSON.parse(raw)
      if (stored && stored.voiceId) return stored.voiceId
    }
  } catch {
    // ignore
  }
  // Fall back to the first available voice
  try {
    const data = await getVoices(lang)
    const first = (data.accents || [])[0]
    return first?.voices?.[0]?.voiceId || null
  } catch {
    return null
  }
}

/**
 * Pronounce a vocab item using the stored/default voice for the language.
 * Convenience for the "Vorsagen" hint (auto-play).
 * @param {{vocabSetId: string, itemId: string, lang: string}} req
 */
export async function pronounceWithStoredVoice({ vocabSetId, itemId, lang }) {
  const voiceId = await resolveVoiceId(lang)
  if (!voiceId) throw new Error('Keine Stimme verfügbar')
  return pronounce({ vocabSetId, itemId, voiceId })
}

export default { getVoices, synthesize, playAudio, pronounce, resolveVoiceId, pronounceWithStoredVoice, _clearCache }
