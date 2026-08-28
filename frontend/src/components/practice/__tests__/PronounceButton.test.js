import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Minimal localStorage mock (jsdom in this project doesn't expose one globally)
const _store = {}
globalThis.localStorage = {
  getItem: (k) => (k in _store ? _store[k] : null),
  setItem: (k, v) => { _store[k] = String(v) },
  removeItem: (k) => { delete _store[k] },
  clear: () => { Object.keys(_store).forEach((k) => delete _store[k]) },
}

// Mock the tts service
vi.mock('@/services/tts', () => ({
  getVoices: vi.fn(),
  pronounce: vi.fn(),
}))

// Mock the toast composable
const showError = vi.fn()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ showError }),
}))

import { getVoices, pronounce } from '@/services/tts'
import PronounceButton from '@/components/practice/PronounceButton.vue'

const VOICES = {
  lang: 'en',
  accents: [
    {
      languageCode: 'en-GB',
      accentName: 'Britisch (en-GB)',
      voices: [
        { voiceId: 'Amy', name: 'Amy', gender: 'Female' },
        { voiceId: 'Brian', name: 'Brian', gender: 'Male' },
      ],
    },
    {
      languageCode: 'en-US',
      accentName: 'Amerikanisch (en-US)',
      voices: [{ voiceId: 'Joanna', name: 'Joanna', gender: 'Female' }],
    },
  ],
}

function makeWrapper() {
  return mount(PronounceButton, {
    props: { vocabSetId: 'vs-1', itemId: 'item-1', lang: 'en' },
  })
}

describe('PronounceButton', () => {
  beforeEach(() => {
    localStorage.clear()
    getVoices.mockReset()
    pronounce.mockReset()
    showError.mockReset()
    getVoices.mockResolvedValue(VOICES)
    pronounce.mockResolvedValue({ addEventListener: vi.fn() })
  })

  it('renders speaker and settings buttons', () => {
    const w = makeWrapper()
    const buttons = w.findAll('button')
    expect(buttons.length).toBe(2)
    expect(w.find('[aria-label="Aussprache anhören"]').exists()).toBe(true)
    expect(w.find('[aria-label="Aussprache-Einstellungen"]').exists()).toBe(true)
  })

  it('opens the popover and loads voices on settings toggle', async () => {
    const w = makeWrapper()
    await w.find('[aria-label="Aussprache-Einstellungen"]').trigger('click')
    await flush()
    expect(getVoices).toHaveBeenCalledWith('en')
    const selects = w.findAll('select')
    expect(selects.length).toBe(2)
    // accent options
    const accentOptions = selects[0].findAll('option')
    expect(accentOptions.map((o) => o.text())).toEqual(['Britisch (en-GB)', 'Amerikanisch (en-US)'])
  })

  it('persists accent/voice selection to localStorage', async () => {
    const w = makeWrapper()
    await w.find('[aria-label="Aussprache-Einstellungen"]').trigger('click')
    await flush()
    const selects = w.findAll('select')
    // select US accent -> should default to Joanna
    await selects[0].setValue('en-US')
    await flush()
    const stored = JSON.parse(localStorage.getItem('vocabgym_tts_en'))
    expect(stored.accent).toBe('en-US')
    expect(stored.voiceId).toBe('Joanna')
  })

  it('preselects stored voice on load', async () => {
    localStorage.setItem('vocabgym_tts_en', JSON.stringify({ accent: 'en-GB', voiceId: 'Brian' }))
    const w = makeWrapper()
    await w.find('[aria-label="Aussprache-Einstellungen"]').trigger('click')
    await flush()
    const selects = w.findAll('select')
    expect(selects[1].element.value).toBe('Brian')
  })

  it('play triggers pronounce with the selected voice', async () => {
    localStorage.setItem('vocabgym_tts_en', JSON.stringify({ accent: 'en-GB', voiceId: 'Brian' }))
    const w = makeWrapper()
    await w.find('[aria-label="Aussprache anhören"]').trigger('click')
    await flush()
    expect(pronounce).toHaveBeenCalledWith({
      vocabSetId: 'vs-1', itemId: 'item-1', voiceId: 'Brian',
    })
  })

  it('shows a rate-limit error toast on 429', async () => {
    const err = new Error('rate')
    err.response = { status: 429 }
    pronounce.mockRejectedValue(err)
    const w = makeWrapper()
    await w.find('[aria-label="Aussprache anhören"]').trigger('click')
    await flush()
    expect(showError).toHaveBeenCalledWith('Zu viele Aussprache-Anfragen, bitte kurz warten.')
  })
})

// Helper: flush pending promises/microtasks
function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}
