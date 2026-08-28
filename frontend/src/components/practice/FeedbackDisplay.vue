<template>
  <div
    class="rounded-lg p-4 text-center"
    :class="correct
      ? 'bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800'
      : 'bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800'"
  >
    <div class="flex items-center justify-center gap-2 mb-2">
      <!-- Correct Icon -->
      <svg v-if="correct" class="w-6 h-6 text-success" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
      </svg>
      <!-- Incorrect Icon -->
      <svg v-else class="w-6 h-6 text-error" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
      </svg>
      <span class="font-semibold" :class="correct ? 'text-green-800 dark:text-green-200' : 'text-red-800 dark:text-red-200'">
        {{ correct ? 'Richtig! 🎉' : 'Leider falsch' }}
      </span>
    </div>

    <!-- Correct word: always shown, at least as large as the source word, so it sticks -->
    <div class="mt-2 mb-1">
      <p class="text-xs text-gray-500 dark:text-gray-400">Richtige Antwort</p>
      <p class="text-3xl font-bold text-green-700 dark:text-green-300 break-words">
        {{ correctAnswer }}
      </p>
    </div>

    <div v-if="!correct" class="mt-2">
      <p class="text-sm text-gray-600 dark:text-gray-300">
        Deine Antwort: <span class="font-medium text-red-700 dark:text-red-300">{{ userAnswer }}</span>
      </p>

      <!-- Gender/Article Error Explanation -->
      <div v-if="genderError" class="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-left">
        <p class="text-sm font-medium text-yellow-800 dark:text-yellow-200">⚠️ Genus-Fehler (falscher Artikel)</p>
        <p class="text-xs text-yellow-700 mt-1">{{ genderError.explanation }}</p>
      </div>

      <!-- Note Input -->
      <div class="mt-3 text-left">
        <button
          v-if="!showNoteInput"
          @click="showNoteInput = true"
          class="text-xs text-primary-600 hover:text-primary-700"
        >
          📝 Notiz hinzufügen (Eselsbrücke)
        </button>
        <div v-else class="flex gap-2">
          <input
            v-model="noteText"
            type="text"
            class="flex-1 text-sm border border-gray-300 rounded px-2 py-1 focus:ring-1 focus:ring-primary-500"
            placeholder="z.B. 'une fiche — weiblich, wie une affiche'"
            @keyup.enter="saveNote"
          />
          <button @click="saveNote" class="text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded hover:bg-primary-200">
            Speichern
          </button>
        </div>
        <p v-if="noteSaved" class="text-xs text-green-600 mt-1">✓ Notiz gespeichert</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '@/services/api'
import { getAllArticleGenders } from '@/utils/languages'

const props = defineProps({
  correct: { type: Boolean, required: true },
  correctAnswer: { type: String, default: '' },
  userAnswer: { type: String, default: '' },
  itemId: { type: String, default: '' },
  vocabSetId: { type: String, default: '' },
  targetLanguage: { type: String, default: 'fr' }
})

const showNoteInput = ref(false)
const noteText = ref('')
const noteSaved = ref(false)

async function saveNote() {
  if (!noteText.value.trim() || !props.itemId) return

  try {
    await api.put(`/vocab/${props.vocabSetId}/items/${props.itemId}`, {
      notes: noteText.value.trim()
    })
    noteSaved.value = true
  } catch {
    // Save locally even if API fails
    noteSaved.value = true
  }
}

const allArticleGenders = computed(() => getAllArticleGenders(props.targetLanguage))

const genderError = computed(() => {
  if (props.correct || !props.userAnswer || !props.correctAnswer) return null

  const userWords = props.userAnswer.trim().toLowerCase().split(' ')
  const correctWords = props.correctAnswer.trim().toLowerCase().split(' ')

  if (userWords.length < 2 || correctWords.length < 2) return null

  const userArticle = userWords[0]
  const correctArticle = correctWords[0]

  if (userArticle === correctArticle) return null

  const allArticles = allArticleGenders.value

  if (!(userArticle in allArticles) || !(correctArticle in allArticles)) return null

  const userRest = userWords.slice(1).join(' ')
  const correctRest = correctWords.slice(1).join(' ')
  const isSameNoun = userRest === correctRest ||
    userRest.normalize('NFD').replace(/[\u0300-\u036f]/g, '') ===
    correctRest.normalize('NFD').replace(/[\u0300-\u036f]/g, '')

  if (!isSameNoun) return null

  return {
    explanation: `Du hast „${userArticle}" geschrieben (${allArticles[userArticle]}), aber das Wort ist ${allArticles[correctArticle]}: „${correctArticle}". Merke dir das Geschlecht zusammen mit dem Wort!`
  }
})
</script>
