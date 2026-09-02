<template>
  <!--
    A standalone, clearly-labelled trigger ("🗣️ Stimme") that opens the
    accent/voice picker. Separated from the play button so both can live as
    equal buttons in the practice action bar. The selection is stored per
    language in localStorage (key vocabgym_tts_<lang>) and shared with every
    other place that pronounces (PronounceButton, the "Vorsagen" button).
  -->
  <span class="relative inline-block">
    <button
      type="button"
      class="btn-secondary text-sm px-3 py-1.5"
      :aria-label="'Stimme & Akzent wählen'"
      title="Stimme & Akzent wählen"
      :aria-expanded="showSettings"
      @click="toggleSettings"
    >
      <span class="mr-1.5" aria-hidden="true">🗣️</span>
      Stimme
    </button>

    <!-- Popover -->
    <div
      v-if="showSettings"
      class="absolute z-50 top-full left-0 mt-1 w-64 rounded-lg bg-white dark:bg-gray-800 shadow-xl border border-gray-200 dark:border-gray-700 p-3 text-left"
      @keydown.esc="closeSettings"
    >
      <p v-if="isLoadingVoices" class="text-sm text-gray-500 dark:text-gray-400">Stimmen werden geladen…</p>
      <p v-else-if="loadError" class="text-sm text-red-600 dark:text-red-400">{{ loadError }}</p>
      <p v-else-if="!accents.length" class="text-sm text-gray-500 dark:text-gray-400">Keine Stimmen verfügbar.</p>
      <template v-else>
        <label class="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Akzent</label>
        <select
          v-model="selectedAccent"
          class="input-field w-full text-sm mb-3"
          @change="onAccentChange"
        >
          <option v-for="a in accents" :key="a.languageCode" :value="a.languageCode">
            {{ a.accentName }}
          </option>
        </select>

        <label class="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Stimme</label>
        <select
          v-model="selectedVoiceId"
          class="input-field w-full text-sm"
          @change="persistSelection"
        >
          <option v-for="v in voicesForAccent" :key="v.voiceId" :value="v.voiceId">
            {{ v.name }}<template v-if="v.gender"> ({{ genderLabel(v.gender) }})</template>
          </option>
        </select>
      </template>
    </div>
  </span>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getVoices } from '@/services/tts'

const props = defineProps({
  lang: { type: String, required: true },
})

const showSettings = ref(false)
const isLoadingVoices = ref(false)
const loadError = ref('')
const accents = ref([])
const selectedAccent = ref('')
const selectedVoiceId = ref('')

const storageKey = computed(() => `vocabgym_tts_${props.lang}`)

const voicesForAccent = computed(() => {
  const group = accents.value.find((a) => a.languageCode === selectedAccent.value)
  return group ? group.voices : []
})

function genderLabel(gender) {
  if (gender === 'Female') return 'weiblich'
  if (gender === 'Male') return 'männlich'
  return gender
}

function loadStoredSelection() {
  try {
    const raw = localStorage.getItem(storageKey.value)
    if (raw) return JSON.parse(raw)
  } catch {
    // ignore parse errors
  }
  return null
}

function persistSelection() {
  try {
    localStorage.setItem(
      storageKey.value,
      JSON.stringify({ accent: selectedAccent.value, voiceId: selectedVoiceId.value })
    )
  } catch {
    // ignore storage errors (private mode etc.)
  }
}

function onAccentChange() {
  const voices = voicesForAccent.value
  selectedVoiceId.value = voices.length ? voices[0].voiceId : ''
  persistSelection()
}

async function ensureVoicesLoaded() {
  if (accents.value.length || isLoadingVoices.value) return
  isLoadingVoices.value = true
  loadError.value = ''
  try {
    const data = await getVoices(props.lang)
    accents.value = data.accents || []

    const stored = loadStoredSelection()
    const storedAccentValid = stored && accents.value.some((a) => a.languageCode === stored.accent)
    if (storedAccentValid) {
      selectedAccent.value = stored.accent
      const group = accents.value.find((a) => a.languageCode === stored.accent)
      const voiceValid = group && group.voices.some((v) => v.voiceId === stored.voiceId)
      selectedVoiceId.value = voiceValid ? stored.voiceId : (group.voices[0]?.voiceId || '')
    } else if (accents.value.length) {
      selectedAccent.value = accents.value[0].languageCode
      selectedVoiceId.value = accents.value[0].voices[0]?.voiceId || ''
    }
  } catch (e) {
    loadError.value = 'Stimmen konnten nicht geladen werden.'
  } finally {
    isLoadingVoices.value = false
  }
}

async function toggleSettings() {
  showSettings.value = !showSettings.value
  if (showSettings.value) {
    await ensureVoicesLoaded()
  }
}

function closeSettings() {
  showSettings.value = false
}
</script>
