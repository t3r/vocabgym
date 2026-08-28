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
    </div>

    <!-- Answer Input -->
    <AnswerInput
      v-if="!feedback"
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
            v-if="question.itemId && question.vocabSetId && answerIsTarget"
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
      :answer-is-target="answerIsTarget"
    />

    <!-- Actions -->
    <div class="mt-6 flex justify-between items-center">
      <div class="flex gap-3">
        <button
          v-if="!feedback"
          @click="$emit('skip')"
          type="button"
          aria-label="Frage überspringen"
          title="Frage überspringen"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <!-- skip-forward icon (double chevron + bar) -->
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M4.5 4.2a1 1 0 0 0-1.5.87v9.86a1 1 0 0 0 1.5.87l6-4.93a1 1 0 0 0 0-1.74l-6-4.93z" />
            <path d="M11 4.2a1 1 0 0 0-1.5.87v9.86a1 1 0 0 0 1.5.87l6-4.93a1 1 0 0 0 0-1.74l-6-4.93z" />
            <rect x="16.5" y="4" width="1.8" height="12" rx="0.9" />
          </svg>
          Überspringen
        </button>
        <button
          v-if="!feedback && (hintEnabled || question.isNew)"
          @click="showHint"
          class="text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          {{ question.isNew ? '💡 Neues Wort — Lösung zeigen' : '💡 Vorsagen' }}
        </button>
        <span
          v-if="!feedback && !hintEnabled && !question.isNew"
          class="text-xs text-gray-400 italic"
        >
          💡 Vorsagen ab 2 richtigen
        </span>
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
        v-if="showingHint"
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import AnswerInput from './AnswerInput.vue'
import FeedbackDisplay from './FeedbackDisplay.vue'
import PronounceButton from './PronounceButton.vue'
import { getLanguageName, getAllArticleGenders } from '@/utils/languages'
import { pronounceWithStoredVoice } from '@/services/tts'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  question: { type: Object, required: true },
  direction: { type: String, default: 'de-fr' },
  feedback: { type: Object, default: null },
  streak: { type: Number, default: 0 },
  hintEnabled: { type: Boolean, default: false },
  targetLanguage: { type: String, default: 'fr' }
})

defineEmits(['submit', 'skip', 'next', 'accept-close', 'reject-close'])

const { showError } = useToast()

const showingHint = ref(false)
let hintTimeout = null

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

  // Also play the pronunciation when the solution is the target-language word
  // (Deutsch -> Fremdsprache). Uses the voice/accent stored by PronounceButton.
  if (answerIsTarget.value && props.question.vocabSetId && props.question.itemId) {
    pronounceWithStoredVoice({
      vocabSetId: props.question.vocabSetId,
      itemId: props.question.itemId,
      lang: props.targetLanguage,
    }).catch((e) => {
      const status = e?.response?.status
      if (status === 429) {
        showError('Zu viele Aussprache-Anfragen, bitte kurz warten.')
      }
      // Silent otherwise — the text hint is still shown.
    })
  }
}
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
