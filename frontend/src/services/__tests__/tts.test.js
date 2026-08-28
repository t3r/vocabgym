import { describe, it, expect, beforeEach, vi } from 'vitest'

// Minimal localStorage mock (jsdom in this project doesn't expose one globally)
const _ls = {}
globalThis.localStorage = {
  getItem: (k) => (k in _ls ? _ls[k] : null),
  setItem: (k, v) => { _ls[k] = String(v) },
  removeItem: (k) => { delete _ls[k] },
  clear: () => { Object.keys(_ls).forEach((k) => delete _ls[k]) },
}

// Mock the api client used by the service
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import api from '@/services/api'
import { getVoices, synthesize, pronounce, playAudio, resolveVoiceId, pronounceWithStoredVoice, _clearCache } from '@/services/tts'

describe('tts service', () => {
  beforeEach(() => {
    _clearCache()
    localStorage.clear()
    api.get.mockReset()
    api.post.mockReset()
  })

  describe('getVoices', () => {
    it('calls GET /tts/voices with lang param and returns data', async () => {
      api.get.mockResolvedValue({ data: { lang: 'en', accents: [] } })
      const data = await getVoices('en')
      expect(api.get).toHaveBeenCalledWith('/tts/voices', { params: { lang: 'en' } })
      expect(data).toEqual({ lang: 'en', accents: [] })
    })
  })

  describe('synthesize', () => {
    it('posts vocabSetId/itemId/voiceId and returns audioUrl', async () => {
      api.post.mockResolvedValue({ data: { audioUrl: 'https://s3/x.mp3', cached: false } })
      const url = await synthesize({ vocabSetId: 'vs', itemId: 'it', voiceId: 'Amy' })
      expect(api.post).toHaveBeenCalledWith('/tts/synthesize', {
        vocabSetId: 'vs', itemId: 'it', voiceId: 'Amy',
      })
      expect(url).toBe('https://s3/x.mp3')
    })

    it('caches the URL and does not call the API twice for the same key', async () => {
      api.post.mockResolvedValue({ data: { audioUrl: 'https://s3/x.mp3' } })
      const req = { vocabSetId: 'vs', itemId: 'it', voiceId: 'Amy' }
      await synthesize(req)
      await synthesize(req)
      expect(api.post).toHaveBeenCalledTimes(1)
    })

    it('does not cache different voices together', async () => {
      api.post
        .mockResolvedValueOnce({ data: { audioUrl: 'https://s3/a.mp3' } })
        .mockResolvedValueOnce({ data: { audioUrl: 'https://s3/b.mp3' } })
      const a = await synthesize({ vocabSetId: 'vs', itemId: 'it', voiceId: 'Amy' })
      const b = await synthesize({ vocabSetId: 'vs', itemId: 'it', voiceId: 'Brian' })
      expect(a).toBe('https://s3/a.mp3')
      expect(b).toBe('https://s3/b.mp3')
      expect(api.post).toHaveBeenCalledTimes(2)
    })
  })

  describe('pronounce', () => {
    it('throws when no audio url is returned', async () => {
      api.post.mockResolvedValue({ data: {} })
      await expect(
        pronounce({ vocabSetId: 'vs', itemId: 'it', voiceId: 'Amy' })
      ).rejects.toThrow()
    })

    it('propagates API errors', async () => {
      api.post.mockRejectedValue(new Error('429'))
      await expect(
        pronounce({ vocabSetId: 'vs', itemId: 'it', voiceId: 'Amy' })
      ).rejects.toThrow('429')
    })
  })

  describe('playAudio', () => {
    it('constructs an Audio element and calls play', async () => {
      const playSpy = vi.fn().mockResolvedValue()
      const OriginalAudio = global.Audio
      global.Audio = vi.fn().mockImplementation(() => ({ play: playSpy }))
      await playAudio('https://s3/x.mp3')
      expect(global.Audio).toHaveBeenCalledWith('https://s3/x.mp3')
      expect(playSpy).toHaveBeenCalled()
      global.Audio = OriginalAudio
    })
  })

  describe('resolveVoiceId', () => {
    it('uses the voice stored in localStorage', async () => {
      localStorage.setItem('vocabgym_tts_en', JSON.stringify({ accent: 'en-GB', voiceId: 'Brian' }))
      const id = await resolveVoiceId('en')
      expect(id).toBe('Brian')
      expect(api.get).not.toHaveBeenCalled()
    })

    it('falls back to the first backend voice when nothing stored', async () => {
      api.get.mockResolvedValue({ data: { accents: [
        { languageCode: 'fr-FR', voices: [{ voiceId: 'Celine' }] },
      ] } })
      const id = await resolveVoiceId('fr')
      expect(id).toBe('Celine')
    })

    it('returns null when no voices available', async () => {
      api.get.mockResolvedValue({ data: { accents: [] } })
      const id = await resolveVoiceId('it')
      expect(id).toBeNull()
    })
  })

  describe('pronounceWithStoredVoice', () => {
    it('resolves the voice then synthesizes', async () => {
      localStorage.setItem('vocabgym_tts_en', JSON.stringify({ accent: 'en-US', voiceId: 'Joanna' }))
      api.post.mockResolvedValue({ data: { audioUrl: 'https://s3/x.mp3' } })
      const playSpy = vi.fn().mockResolvedValue()
      const OriginalAudio = global.Audio
      global.Audio = vi.fn().mockImplementation(() => ({ play: playSpy }))
      await pronounceWithStoredVoice({ vocabSetId: 'vs', itemId: 'it', lang: 'en' })
      expect(api.post).toHaveBeenCalledWith('/tts/synthesize', {
        vocabSetId: 'vs', itemId: 'it', voiceId: 'Joanna',
      })
      global.Audio = OriginalAudio
    })

    it('throws when no voice is available', async () => {
      api.get.mockResolvedValue({ data: { accents: [] } })
      await expect(
        pronounceWithStoredVoice({ vocabSetId: 'vs', itemId: 'it', lang: 'it' })
      ).rejects.toThrow()
    })
  })
})
