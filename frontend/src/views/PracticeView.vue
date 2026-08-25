<template>
  <!-- Practice view: Question display, answer input, progress bar, session summary -->
  <div class="max-w-2xl mx-auto px-4 sm:px-6 py-8">
    <!-- Session Setup (before start) -->
    <div v-if="!practiceStore.isSessionActive && !practiceStore.sessionResults" class="card">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">Übung starten</h1>

      <div class="space-y-4 mb-6">
        <div>
          <label class="label">Richtung</label>
          <select v-model="direction" class="input-field">
            <option value="de-fr">Deutsch → Französisch</option>
            <option value="fr-de">Französisch → Deutsch</option>
          </select>
        </div>
      </div>

      <button @click="startPractice" class="btn-primary w-full" :disabled="isStarting">
        {{ isStarting ? 'Wird geladen...' : 'Übung starten' }}
      </button>
    </div>

    <!-- Active Session -->
    <div v-else-if="practiceStore.isSessionActive">
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
        :hint-enabled="practiceStore.currentStreak >= 2"
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
import { ref, onBeforeUnmount } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { usePracticeStore } from '@/stores/practice'
import { useToast } from '@/composables/useToast'
import ProgressBar from '@/components/practice/ProgressBar.vue'
import QuestionCard from '@/components/practice/QuestionCard.vue'
import SessionSummary from '@/components/practice/SessionSummary.vue'

const props = defineProps({
  vocabSetId: { type: String, required: true }
})

const router = useRouter()
const practiceStore = usePracticeStore()
const { showError } = useToast()

const direction = ref('de-fr')
const isStarting = ref(false)
const feedback = ref(null)

async function startPractice() {
  isStarting.value = true
  feedback.value = null
  try {
    await practiceStore.startSession(props.vocabSetId, {
      direction: direction.value
    })
  } catch (err) {
    showError(err.message || 'Fehler beim Starten der Übung')
  } finally {
    isStarting.value = false
  }
}

function handleSubmit(answer) {
  const result = practiceStore.submitAnswer(answer)
  if (result) {
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
    practiceStore.endSession()
  }
}

// Warn before leaving active session
onBeforeRouteLeave(async (to, from, next) => {
  if (practiceStore.isSessionActive) {
    const leave = confirm('Möchtest du die Übung wirklich beenden?')
    if (!leave) return next(false)
    // Save partial progress before leaving
    await practiceStore.endSession()
  }
  next()
})

onBeforeUnmount(() => {
  // endSession already called in onBeforeRouteLeave, just reset local state
  if (practiceStore.isSessionActive) {
    practiceStore.resetSession()
  }
})
</script>
