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
        <p class="text-3xl font-bold text-green-700 dark:text-green-300 break-words">
          {{ feedback.correctAnswer }}
        </p>
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
    />

    <!-- Actions -->
    <div class="mt-6 flex justify-between items-center">
      <div class="flex gap-3">
        <button
          v-if="!feedback"
          @click="$emit('skip')"
          class="text-sm text-gray-500 hover:text-gray-700"
        >
          Überspringen
        </button>
        <button
          v-if="!feedback && hintEnabled"
          @click="showHint"
          class="text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          💡 Vorsagen
        </button>
        <span
          v-if="!feedback && !hintEnabled"
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
        class="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-center"
      >
        <p class="text-sm text-blue-800 dark:text-blue-200">
          💡 <span class="font-medium">{{ correctAnswerText }}</span>
        </p>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import AnswerInput from './AnswerInput.vue'
import FeedbackDisplay from './FeedbackDisplay.vue'
import { getLanguageName, getAllArticleGenders } from '@/utils/languages'

const props = defineProps({
  question: { type: Object, required: true },
  direction: { type: String, default: 'de-fr' },
  feedback: { type: Object, default: null },
  streak: { type: Number, default: 0 },
  hintEnabled: { type: Boolean, default: false },
  targetLanguage: { type: String, default: 'fr' }
})

defineEmits(['submit', 'skip', 'next', 'accept-close', 'reject-close'])

const showingHint = ref(false)
let hintTimeout = null

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
