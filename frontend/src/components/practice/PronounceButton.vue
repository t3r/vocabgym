<template>
  <span class="relative inline-flex items-center gap-1 align-middle">
    <!-- Speaker / play button -->
    <button
      type="button"
      class="p-1 rounded-md text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
      :aria-label="'Aussprache anhören'"
      :title="'Aussprache anhören'"
      :disabled="isPlaying || isLoading"
      @click="play"
    >
      <!-- loading spinner -->
      <svg v-if="isPlaying || isLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <!-- speaker icon -->
      <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
      </svg>
    </button>

    <!-- Settings toggle (accent/voice) -->
    <button
      type="button"
      class="p-0.5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
      :aria-label="'Aussprache-Einstellungen'"
      :title="'Stimme & Akzent wählen'"
      :aria-expanded="showSettings"
      @click="toggleSettings"
    >
      <svg class="w-4 h-4 transition-transform" :class="showSettings ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Popover -->
    <div
      v-if="showSettings"
      ref="popover"
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
import { getVoices, pronounce } from '@/services/tts'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  vocabSetId: { type: String, required: true },
  itemId: { type: String, required: true },
  lang: { type: String, required: true },
})

const { showError } = useToast()

const showSettings = ref(false)
const isLoadingVoices = ref(false)
const loadError = ref('')
const accents = ref([])
const selectedAccent = ref('')
const selectedVoiceId = ref('')
const isPlaying = ref(false)
const isLoading = ref(false)
const popover = ref(null)

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
  // Pick the first voice of the newly selected accent
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

    // Restore stored selection or default to first accent/voice
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

async function play() {
  if (isPlaying.value || isLoading.value) return
  isLoading.value = true
  try {
    // Make sure we have a voice selected (lazy-load on first play)
    await ensureVoicesLoaded()
    if (!selectedVoiceId.value) {
      showError('Keine Stimme verfügbar.')
      return
    }
    isPlaying.value = true
    const audio = await pronounce({
      vocabSetId: props.vocabSetId,
      itemId: props.itemId,
      voiceId: selectedVoiceId.value,
    })
    // Reset playing state when audio finishes
    if (audio && typeof audio.addEventListener === 'function') {
      audio.addEventListener('ended', () => { isPlaying.value = false })
      audio.addEventListener('error', () => { isPlaying.value = false })
    } else {
      isPlaying.value = false
    }
  } catch (e) {
    const status = e?.response?.status
    if (status === 429) {
      showError('Zu viele Aussprache-Anfragen, bitte kurz warten.')
    } else {
      showError('Aussprache konnte nicht abgespielt werden.')
    }
    isPlaying.value = false
  } finally {
    isLoading.value = false
  }
}
</script>
