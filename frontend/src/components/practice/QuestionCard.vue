<template>
  <div class="card">
    <!-- Streak Display -->
    <div v-if="streak > 0" class="flex justify-end mb-2">
      <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200">
        🔥 {{ streak }} richtig in Folge
      </span>
    </div>

    <!-- Question Display -->
    <div class="text-center mb-8">
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">
        {{ (direction === 'de-fr' || direction === 'source-target') ? `Übersetze ins ${getLanguageName(targetLanguage)}:` : 'Übersetze ins Deutsche:' }}
      </p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">
        {{ question.question || ((direction === 'de-fr' || direction === 'source-target') ? (question.source || question.german) : (question.target || question.french)) }}
      </p>

      <!-- AI comic thumbnail illustrating the word's meaning. A learning aid,
           so it is hidden in exam mode (like Vorsagen / the solution). While the
           worker generates (first time per word) a pulsing placeholder with a
           spinner shows activity; once ready the image replaces it. Nothing is
           shown on failure/rate-limit. -->
      <div v-if="!examMode && (thumbnailUrl || thumbnailLoading)" class="mt-4 flex justify-center">
        <img
          v-if="thumbnailUrl"
          :src="thumbnailUrl"
          alt="Bild zum Wort"
          class="w-32 h-32 rounded-lg object-cover shadow-sm bg-gray-50 dark:bg-gray-700"
          loading="lazy"
        />
        <div
          v-else
          class="w-32 h-32 rounded-lg bg-gray-100 dark:bg-gray-700 flex flex-col items-center justify-center gap-2 animate-pulse"
          role="status"
          aria-label="Bild wird erstellt"
        >
          <svg class="w-6 h-6 animate-spin text-primary-500" fill="none" viewBox="0 0 24 24" aria-hidden="true">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span class="text-xs text-gray-500 dark:text-gray-400">🎨 Bild wird erstellt…</span>
        </div>
      </div>
    </div>

    <!-- Answer Input -->
    <AnswerInput
      v-if="!feedback"
      :key="question.questionId ?? question.itemId"
      @submit="$emit('submit', $event)"
      :placeholder="(direction === 'de-fr' || direction === 'source-target') ? `${getLanguageName(targetLanguage)} eingeben...` : 'Deutsch eingeben...'"
    />

    <!-- Almost Correct - Let User Decide -->
    <div v-if="feedback && feedback.close" class="rounded-lg p-4 text-center bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800">
      <p class="font-semibold text-yellow-800 mb-2">Fast richtig!</p>
      <p class="text-sm text-gray-600 dark:text-gray-300">
        Deine Antwort: <span class="font-medium">{{ feedback.userAnswer }}</span>
      </p>
      <div class="mt-2">
        <p class="text-xs text-gray-500 dark:text-gray-400">Richtig wäre</p>
        <div class="flex items-center justify-center gap-2">
          <p class="text-3xl font-bold text-green-700 dark:text-green-300 break-words">
            {{ feedback.correctAnswer }}
          </p>
          <PronounceButton
            v-if="!examMode && question.itemId && question.vocabSetId && answerIsTarget"
            :vocab-set-id="question.vocabSetId"
            :item-id="question.itemId"
            :lang="targetLanguage"
          />
        </div>
      </div>
      <!-- Gender Error Explanation -->
      <div v-if="genderError" class="mt-3 p-2 bg-yellow-100 dark:bg-yellow-900/30 border border-yellow-300 dark:border-yellow-700 rounded text-left">
        <p class="text-sm font-medium text-yellow-800 dark:text-yellow-200">⚠️ Genus-Fehler (falscher Artikel)</p>
        <p class="text-xs text-yellow-700 mt-1">{{ genderError }}</p>
      </div>
      <div class="mt-4 flex justify-center gap-3">
        <button @click="$emit('accept-close')" class="px-4 py-2 bg-green-100 text-green-800 rounded-md hover:bg-green-200 font-medium text-sm">
          ✓ Als richtig werten
        </button>
        <button @click="$emit('reject-close')" class="px-4 py-2 bg-red-100 text-red-800 rounded-md hover:bg-red-200 font-medium text-sm">
          ✗ Als falsch werten
        </button>
      </div>
    </div>

    <!-- Correct/Wrong Feedback -->
    <FeedbackDisplay
      v-if="feedback && !feedback.close"
      :correct="feedback.correct"
      :correct-answer="feedback.correctAnswer"
      :user-answer="feedback.userAnswer"
      :item-id="question.itemId"
      :vocab-set-id="question.vocabSetId || ''"
      :target-language="targetLanguage"
      :answer-is-target="answerIsTarget && !examMode"
    />

    <!-- Actions -->
    <div class="mt-6 flex justify-between items-center">
      <!-- Equal-weight button bar. Überspringen is secondary; the learning aids
           (Lösung zeigen / Vorsagen) are primary. Hidden entirely in exam mode
           except Überspringen. -->
      <div class="flex flex-wrap gap-2 items-center">
        <button
          v-if="!feedback"
          @click="$emit('skip')"
          type="button"
          aria-label="Frage überspringen"
          title="Frage überspringen"
          class="btn-secondary text-sm px-3 py-1.5"
        >
          <span class="mr-1.5" aria-hidden="true">⏭️</span>
          Überspringen
        </button>

        <!-- Text reveal. Gated behind a 2-streak (or a new word): when locked,
             it is shown as a disabled button with an explanatory tooltip rather
             than hidden, so the option stays discoverable. -->
        <button
          v-if="!feedback && !examMode"
          @click="showHint"
          type="button"
          :disabled="!(hintEnabled || question.isNew)"
          :title="(hintEnabled || question.isNew) ? 'Lösung anzeigen' : 'Verfügbar ab 2 richtigen in Folge'"
          class="btn-primary text-sm px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span class="mr-1.5" aria-hidden="true">💡</span>
          {{ question.isNew ? 'Neues Wort — Lösung zeigen' : 'Lösung zeigen' }}
        </button>

        <!-- Pronounce (always available in learning mode when the solution is
             the target-language word). -->
        <button
          v-if="!feedback && !examMode && answerIsTarget && question.itemId && question.vocabSetId"
          @click="playPronunciation"
          :disabled="pronouncing"
          type="button"
          aria-label="Aussprache vorsagen"
          title="Aussprache vorsagen"
          class="btn-primary text-sm px-3 py-1.5 disabled:opacity-50"
        >
          <span class="mr-1.5" aria-hidden="true">🔊</span>
          Vorsagen
        </button>

        <!-- Voice / accent picker as its own clearly-labelled button. -->
        <VoicePicker
          v-if="!feedback && !examMode && answerIsTarget && question.itemId && question.vocabSetId"
          :lang="targetLanguage"
        />

        <!-- Eselsbrücke (mnemonic note): only when the item has a saved note. -->
        <button
          v-if="!examMode && question.notes"
          @click="showingNote = !showingNote"
          type="button"
          aria-label="Eselsbrücke anzeigen"
          class="btn-secondary text-sm px-3 py-1.5"
        >
          <span class="mr-1.5" aria-hidden="true">💭</span>
          Eselsbrücke
        </button>
      </div>
      <div v-if="!feedback"></div>

      <button
        v-if="feedback && !feedback.close"
        @click="$emit('next')"
        class="btn-primary"
      >
        Weiter →
      </button>
    </div>

    <!-- Hint Toast -->
    <transition name="hint-fade">
      <div
        v-if="showingHint && !examMode"
        class="mt-4 p-3 bg-blue-50 dark:bg-blue-900/40 border border-blue-200 dark:border-blue-700 rounded-lg text-center"
      >
        <p class="text-xs text-blue-700 dark:text-blue-300 mb-1">💡 Lösung</p>
        <div class="flex items-center justify-center gap-2">
          <p class="text-2xl font-bold text-blue-900 dark:text-blue-100 break-words">
            {{ correctAnswerText }}
          </p>
          <PronounceButton
            v-if="answerIsTarget && question.itemId && question.vocabSetId"
            :vocab-set-id="question.vocabSetId"
            :item-id="question.itemId"
            :lang="targetLanguage"
          />
        </div>
      </div>
    </transition>

    <!-- Eselsbrücke note display -->
    <transition name="hint-fade">
      <div
        v-if="showingNote && question.notes && !examMode"
        class="mt-4 p-3 bg-purple-50 dark:bg-purple-900/40 border border-purple-200 dark:border-purple-700 rounded-lg text-center"
      >
        <p class="text-xs text-purple-700 dark:text-purple-300 mb-1">💭 Eselsbrücke</p>
        <p class="text-lg font-medium text-purple-900 dark:text-purple-100 break-words">
          {{ question.notes }}
        </p>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import AnswerInput from './AnswerInput.vue'
import FeedbackDisplay from './FeedbackDisplay.vue'
import PronounceButton from './PronounceButton.vue'
import VoicePicker from './VoicePicker.vue'
import { getLanguageName, getAllArticleGenders } from '@/utils/languages'
import { pronounceWithStoredVoice } from '@/services/tts'
import { fetchThumbnail } from '@/services/thumbnail'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  question: { type: Object, required: true },
  direction: { type: String, default: 'de-fr' },
  feedback: { type: Object, default: null },
  streak: { type: Number, default: 0 },
  hintEnabled: { type: Boolean, default: false },
  targetLanguage: { type: String, default: 'fr' },
  examMode: { type: Boolean, default: false }
})

const emit = defineEmits(['submit', 'skip', 'next', 'accept-close', 'reject-close'])

const { showError } = useToast()

// Allow advancing with the Enter key once feedback is shown (the answer input
// is gone by then, so its own Enter-to-submit no longer applies). Only for the
// exact/wrong feedback with a "Weiter" button — a "close" result needs an
// explicit accept/reject decision.
function onKeydown(e) {
  if (e.key !== 'Enter') return
  if (props.feedback && !props.feedback.close) {
    e.preventDefault()
    emit('next')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

// AI comic thumbnail illustrating the current word's meaning. Loaded lazily per
// question; only in practice mode (a picture of the meaning is a hint, so it is
// suppressed in exam mode). Failures/pending resolve to null → no image shown.
const thumbnailUrl = ref(null)
const thumbnailLoading = ref(false)

async function loadThumbnail() {
  thumbnailUrl.value = null
  thumbnailLoading.value = false
  if (props.examMode) return
  const { itemId, vocabSetId } = props.question || {}
  if (!itemId || !vocabSetId) return
  const requestedId = itemId
  const url = await fetchThumbnail({
    vocabSetId,
    itemId,
    // Show the activity indicator while the worker generates (cache miss).
    // Guard against a stale question having moved on.
    onPending: () => {
      if (props.question?.itemId === requestedId) thumbnailLoading.value = true
    },
  })
  // Guard against a late response arriving after the question already changed.
  if (props.question?.itemId === requestedId) {
    thumbnailUrl.value = url
    thumbnailLoading.value = false
  }
}

onMounted(loadThumbnail)

const showingHint = ref(false)
const showingNote = ref(false)
const pronouncing = ref(false)
let hintTimeout = null

// Play the target-language pronunciation with the stored/default voice. Used by
// the "Vorsagen" button in the action bar (voice is chosen via VoicePicker).
function playPronunciation() {
  if (pronouncing.value) return
  if (!(answerIsTarget.value && props.question.vocabSetId && props.question.itemId)) return
  pronouncing.value = true
  pronounceWithStoredVoice({
    vocabSetId: props.question.vocabSetId,
    itemId: props.question.itemId,
    lang: props.targetLanguage,
  })
    .catch((e) => {
      const status = e?.response?.status
      if (status === 429) {
        showError('Zu viele Aussprache-Anfragen, bitte kurz warten.')
      } else {
        showError('Aussprache konnte nicht abgespielt werden.')
      }
    })
    .finally(() => {
      pronouncing.value = false
    })
}

// The correct answer is the target-language word only when translating
// Deutsch -> Fremdsprache. In the reverse direction it is the German word,
// which must not be pronounced with a foreign voice.
const answerIsTarget = computed(() =>
  props.direction === 'de-fr' || props.direction === 'source-target'
)

const correctAnswerText = computed(() => {
  return props.question.correctAnswer
    || ((props.direction === 'de-fr' || props.direction === 'source-target') ? (props.question.target || props.question.french) : (props.question.source || props.question.german))
    || ''
})

const genderError = computed(() => {
  if (!props.feedback || !props.feedback.userAnswer || !props.feedback.correctAnswer) return null
  if (props.feedback.correct) return null

  const userWords = props.feedback.userAnswer.trim().toLowerCase().split(' ')
  const correctWords = props.feedback.correctAnswer.trim().toLowerCase().split(' ')

  if (userWords.length < 2 || correctWords.length < 2) return null

  const userArticle = userWords[0]
  const correctArticle = correctWords[0]

  if (userArticle === correctArticle) return null

  const articleGenders = getAllArticleGenders(props.targetLanguage)

  if (!(userArticle in articleGenders) || !(correctArticle in articleGenders)) return null

  // Check if the rest of the word is similar (only article differs)
  const userRest = userWords.slice(1).join(' ')
  const correctRest = correctWords.slice(1).join(' ')
  const isSameNoun = userRest === correctRest ||
    userRest.normalize('NFD').replace(/[\u0300-\u036f]/g, '') ===
    correctRest.normalize('NFD').replace(/[\u0300-\u036f]/g, '')

  if (!isSameNoun) return null

  return `Du hast „${userArticle}" geschrieben (${articleGenders[userArticle]}), aber das Wort ist ${articleGenders[correctArticle]}: „${correctArticle}".`
})

function showHint() {
  showingHint.value = true
  if (hintTimeout) clearTimeout(hintTimeout)
  hintTimeout = setTimeout(() => {
    showingHint.value = false
  }, 5000)
  // Note: pronunciation is NOT auto-played here. The learner starts audio
  // explicitly via the speaker button (PronounceButton) inside the hint toast.
}

// Reset toggles when the question changes so stale hints/notes don't linger.
watch(() => props.question?.questionId, () => {
  showingHint.value = false
  showingNote.value = false
  loadThumbnail()
})
</script>

<style scoped>
.hint-fade-enter-active,
.hint-fade-leave-active {
  transition: opacity 0.3s ease;
}
.hint-fade-enter-from,
.hint-fade-leave-to {
  opacity: 0;
}
</style>
