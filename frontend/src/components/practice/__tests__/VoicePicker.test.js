import { mount, flushPromises } from '@vue/test-utils'

// Minimal localStorage mock (jsdom in this project doesn't expose one globally)
const _store = {}
globalThis.localStorage = {
  getItem: (k) => (k in _store ? _store[k] : null),
  setItem: (k, v) => { _store[k] = String(v) },
  removeItem: (k) => { delete _store[k] },
  clear: () => { Object.keys(_store).forEach((k) => delete _store[k]) },
}

vi.mock('@/services/tts', () => ({
  getVoices: vi.fn(),
}))

import { getVoices } from '@/services/tts'
import VoicePicker from '@/components/practice/VoicePicker.vue'

const VOICES = {
  lang: 'fr',
  accents: [
    {
      languageCode: 'fr-FR',
      accentName: 'Französisch (fr-FR)',
      voices: [
        { voiceId: 'Lea', name: 'Léa', gender: 'Female' },
        { voiceId: 'Mathieu', name: 'Mathieu', gender: 'Male' },
      ],
    },
    {
      languageCode: 'fr-CA',
      accentName: 'Kanadisch (fr-CA)',
      voices: [{ voiceId: 'Chantal', name: 'Chantal', gender: 'Female' }],
    },
  ],
}

describe('VoicePicker', () => {
  beforeEach(() => {
    localStorage.clear()
    getVoices.mockReset()
  })

  it('shows a clearly labelled "Stimme" trigger button', () => {
    const wrapper = mount(VoicePicker, { props: { lang: 'fr' } })
    expect(wrapper.text()).toContain('Stimme')
    // Popover is not open until clicked.
    expect(wrapper.text()).not.toContain('Akzent')
  })

  it('loads and renders accent + voice selects when opened', async () => {
    getVoices.mockResolvedValue(VOICES)
    const wrapper = mount(VoicePicker, { props: { lang: 'fr' } })
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(getVoices).toHaveBeenCalledWith('fr')
    const selects = wrapper.findAll('select')
    expect(selects).toHaveLength(2) // accent + voice
    expect(wrapper.text()).toContain('Französisch (fr-FR)')
    expect(wrapper.text()).toContain('Léa')
  })

  it('persists the chosen voice to localStorage', async () => {
    getVoices.mockResolvedValue(VOICES)
    const wrapper = mount(VoicePicker, { props: { lang: 'fr' } })
    await wrapper.find('button').trigger('click')
    await flushPromises()

    const [accentSel, voiceSel] = wrapper.findAll('select')
    await voiceSel.setValue('Mathieu')

    const stored = JSON.parse(localStorage.getItem('vocabgym_tts_fr'))
    expect(stored.voiceId).toBe('Mathieu')
    expect(stored.accent).toBe('fr-FR')
  })

  it('restores a previously stored selection', async () => {
    localStorage.setItem('vocabgym_tts_fr', JSON.stringify({ accent: 'fr-CA', voiceId: 'Chantal' }))
    getVoices.mockResolvedValue(VOICES)
    const wrapper = mount(VoicePicker, { props: { lang: 'fr' } })
    await wrapper.find('button').trigger('click')
    await flushPromises()

    const [accentSel, voiceSel] = wrapper.findAll('select')
    expect(accentSel.element.value).toBe('fr-CA')
    expect(voiceSel.element.value).toBe('Chantal')
  })

  it('changing accent picks that accent\'s first voice', async () => {
    getVoices.mockResolvedValue(VOICES)
    const wrapper = mount(VoicePicker, { props: { lang: 'fr' } })
    await wrapper.find('button').trigger('click')
    await flushPromises()

    const [accentSel] = wrapper.findAll('select')
    await accentSel.setValue('fr-CA')

    const stored = JSON.parse(localStorage.getItem('vocabgym_tts_fr'))
    expect(stored.accent).toBe('fr-CA')
    expect(stored.voiceId).toBe('Chantal')
  })

  it('shows an error message when voices fail to load', async () => {
    getVoices.mockRejectedValue(new Error('boom'))
    const wrapper = mount(VoicePicker, { props: { lang: 'fr' } })
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Stimmen konnten nicht geladen werden.')
  })
})
