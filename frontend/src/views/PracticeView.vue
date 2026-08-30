<template>
  <!-- Practice view: Question display, answer input, progress bar, session summary -->
  <div class="max-w-2xl mx-auto px-4 sm:px-6 py-8">
    <!-- Session Setup (before start) -->
    <div v-if="!practiceStore.isSessionActive && !practiceStore.sessionResults" class="card">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">Übung starten</h1>

      <div class="space-y-4 mb-6">
        <div>
          <label class="label">Modus</label>
          <select v-model="mode" class="input-field">
            <option value="practice">📚 Übung (mit Vorsagen & Lösung)</option>
            <option value="exam">⏱️ Prüfung auf Zeit</option>
          </select>
          <p v-if="mode === 'exam'" class="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Im Prüfungsmodus läuft die Zeit. Keine Vorsagen, keine Lösungsanzeige,
            knappe Treffer zählen als falsch. So trainierst du unter Stress.
          </p>
        </div>
        <div>
          <label class="label">Richtung</label>
          <select v-model="direction" class="input-field">
            <option value="source-target">Deutsch → {{ getLanguageName(targetLanguage) }}</option>
            <option value="target-source">{{ getLanguageName(targetLanguage) }} → Deutsch</option>
          </select>
        </div>
      </div>

      <button @click="startPractice" class="btn-primary w-full" :disabled="isStarting">
        {{ isStarting ? 'Wird geladen...' : (mode === 'exam' ? 'Prüfung starten' : 'Übung starten') }}
      </button>
    </div>

    <!-- Active Session -->
    <div v-else-if="practiceStore.isSessionActive">
      <!-- Exam timer (always visible, counts up, stops after last word) -->
      <div v-if="practiceStore.isExam" class="flex justify-center mb-4">
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800">
          <span class="text-lg" aria-hidden="true">⏱️</span>
          <span class="font-mono text-xl font-bold text-red-700 dark:text-red-300 tabular-nums" aria-label="Verstrichene Zeit">
            {{ formattedElapsed }}
          </span>
        </div>
      </div>

      <!-- Progress Bar -->
      <ProgressBar
        :current="practiceStore.progress.current"
        :total="practiceStore.progress.total"
        class="mb-6"
      />

      <!-- Question Card -->
      <QuestionCard
        v-if="practiceStore.currentQuestion"
        :question="practiceStore.currentQuestion"
        :direction="direction"
        :feedback="feedback"
        :streak="practiceStore.currentStreak"
        :hint-enabled="!practiceStore.isExam && practiceStore.currentStreak >= 2"
        :target-language="targetLanguage"
        :exam-mode="practiceStore.isExam"
        @submit="handleSubmit"
        @skip="handleSkip"
        @next="handleNext"
        @accept-close="handleAcceptClose"
        @reject-close="handleRejectClose"
      />
    </div>

    <!-- Session Results -->
    <SessionSummary
      v-else-if="practiceStore.sessionResults"
      :results="practiceStore.sessionResults"
      @practice-again="startPractice"
      @back="router.push({ name: 'Dashboard' })"
    />
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { usePracticeStore } from '@/stores/practice'
import { useVocabStore } from '@/stores/vocab'
import { useToast } from '@/composables/useToast'
import { getLanguageName } from '@/utils/languages'
import ProgressBar from '@/components/practice/ProgressBar.vue'
import QuestionCard from '@/components/practice/QuestionCard.vue'
import SessionSummary from '@/components/practice/SessionSummary.vue'

const props = defineProps({
  vocabSetId: { type: String, required: true }
})

const router = useRouter()
const practiceStore = usePracticeStore()
const vocabStore = useVocabStore()
const { showError } = useToast()

const direction = ref('source-target')
const mode = ref('practice')
const isStarting = ref(false)
const feedback = ref(null)
const targetLanguage = ref('fr')

// Exam timer (counts up); stopped after the last word.
const elapsed = ref(0)
let timerInterval = null

const formattedElapsed = computed(() => {
  const s = elapsed.value
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

function startTimer() {
  stopTimer()
  elapsed.value = 0
  timerInterval = setInterval(() => { elapsed.value += 1 }, 1000)
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

// Load vocab set to get targetLanguage
async function loadVocabSetMeta() {
  try {
    const data = await vocabStore.fetchVocabSet(props.vocabSetId)
    if (data?.targetLanguage) {
      targetLanguage.value = data.targetLanguage
    }
  } catch {
    // fallback to 'fr'
  }
}
loadVocabSetMeta()

async function startPractice() {
  isStarting.value = true
  feedback.value = null
  stopTimer()
  try {
    // Map new direction values to legacy for backend compatibility
    let apiDirection = direction.value
    if (apiDirection === 'source-target') apiDirection = 'de-fr'
    if (apiDirection === 'target-source') apiDirection = 'fr-de'

    await practiceStore.startSession(props.vocabSetId, {
      direction: apiDirection,
      mode: mode.value
    })
    if (mode.value === 'exam') {
      startTimer()
    }
  } catch (err) {
    showError(err.message || 'Fehler beim Starten der Übung')
  } finally {
    isStarting.value = false
  }
}

function handleSubmit(answer) {
  const result = practiceStore.submitAnswer(answer)
  if (result) {
    // Exam mode is strict: an "almost correct" answer counts as WRONG with no
    // accept/reject dialog, keeping the timed flow uninterrupted.
    if (practiceStore.isExam && result.result === 'close') {
      practiceStore.rejectCloseAnswer()
      feedback.value = { correct: false, correctAnswer: result.correctAnswer, userAnswer: result.userAnswer }
      return
    }
    if (result.result === 'exact') {
      feedback.value = { correct: true, correctAnswer: result.correctAnswer, userAnswer: result.userAnswer }
    } else if (result.result === 'close') {
      feedback.value = { close: true, correct: false, correctAnswer: result.correctAnswer, userAnswer: result.userAnswer }
    } else {
      feedback.value = { correct: false, correctAnswer: result.correctAnswer, userAnswer: result.userAnswer }
    }
  }
}

function handleAcceptClose() {
  practiceStore.acceptCloseAnswer()
  feedback.value = { ...feedback.value, correct: true, close: false }
}

function handleRejectClose() {
  practiceStore.rejectCloseAnswer()
  feedback.value = { ...feedback.value, correct: false, close: false }
}

function handleSkip() {
  practiceStore.skipQuestion()
  feedback.value = null
}

function handleNext() {
  feedback.value = null
  const hasNext = practiceStore.nextQuestion()
  if (!hasNext) {
    stopTimer()
    practiceStore.endSession()
  }
}

// Warn before leaving active session
onBeforeRouteLeave(async (to, from, next) => {
  if (practiceStore.isSessionActive) {
    const leave = confirm('Möchtest du die Übung wirklich beenden?')
    if (!leave) return next(false)
    // Save partial progress before leaving
    stopTimer()
    await practiceStore.endSession()
  }
  next()
})

onBeforeUnmount(() => {
  stopTimer()
  // endSession already called in onBeforeRouteLeave, just reset local state
  if (practiceStore.isSessionActive) {
    practiceStore.resetSession()
  }
})
</script>
