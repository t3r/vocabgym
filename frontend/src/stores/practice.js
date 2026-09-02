import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { checkAnswer } from '@/utils/fuzzyMatch'
import {
  saveLiveSession,
  loadLiveSession,
  clearLiveSession,
  enqueuePending,
  removePending,
  sendComplete,
  isNetworkError,
} from '@/services/practiceSync'

export const usePracticeStore = defineStore('practice', () => {
  const currentSession = ref(null)
  const questions = ref([])
  const currentQuestionIndex = ref(0)
  const answers = ref([])
  // itemIds the learner skipped during this session (deduplicated). Used to
  // record "repeatedly skipped" words server-side so the focused ("nur
  // Schwachstellen") session can surface them. Only items that were skipped
  // AND never actually answered are reported as skips at completion.
  const skippedItemIds = ref([])
  const sessionResults = ref(null)
  const isSessionActive = ref(false)
  const currentStreak = ref(0)
  // True while a completed session could not be sent (network) and is queued
  // for later recovery — the UI shows a "will be saved later" state instead of
  // pretending the result was stored.
  const savePending = ref(false)

  /**
   * Persist the in-progress session to localStorage so a reload/crash/offline
   * doesn't lose the learner's answers. Called after every state mutation.
   */
  function persistLive() {
    if (isSessionActive.value && currentSession.value) {
      saveLiveSession({
        currentSession: currentSession.value,
        questions: questions.value,
        currentQuestionIndex: currentQuestionIndex.value,
        answers: answers.value,
        currentStreak: currentStreak.value,
        skippedItemIds: skippedItemIds.value,
      })
    }
  }

  const currentQuestion = computed(() => {
    if (!questions.value.length || currentQuestionIndex.value >= questions.value.length) {
      return null
    }
    return questions.value[currentQuestionIndex.value]
  })

  const mode = computed(() => currentSession.value?.mode || 'practice')
  const isExam = computed(() => mode.value === 'exam')

  const progress = computed(() => ({
    current: currentQuestionIndex.value + 1,
    total: questions.value.length,
    percentage: questions.value.length
      ? Math.round(((currentQuestionIndex.value + 1) / questions.value.length) * 100)
      : 0
  }))

  const score = computed(() => {
    const correct = answers.value.filter((a) => a.correct).length
    const total = answers.value.length
    return {
      correct,
      total,
      percentage: total ? Math.round((correct / total) * 100) : 0
    }
  })

  async function startSession(vocabSetId, options = {}) {
    try {
      const response = await api.post('/practice/start', {
        vocabSetId,
        direction: options.direction || 'de-fr',
        questionCount: options.questionCount || 10,
        mode: options.mode || 'practice',
        focus: options.focus || 'all'
      })

      currentSession.value = {
        sessionId: response.data.sessionId,
        vocabSetId,
        direction: options.direction || 'de-fr',
        mode: options.mode || 'practice',
        focus: options.focus || 'all',
        startTime: Date.now()
      }
      // Ensure every question carries its vocabSetId (used e.g. by the
      // pronunciation button, which requests TTS by vocabSetId + itemId).
      questions.value = (response.data.questions || []).map((q) => ({
        ...q,
        vocabSetId: q.vocabSetId || vocabSetId,
      }))
      currentQuestionIndex.value = 0
      answers.value = []
      skippedItemIds.value = []
      sessionResults.value = null
      isSessionActive.value = true
      savePending.value = false
      persistLive()

      return response.data
    } catch (err) {
      throw new Error(err.response?.data?.message || 'Fehler beim Starten der Übung')
    }
  }

  function submitAnswer(userAnswer) {
    const question = currentQuestion.value
    if (!question) return null

    const correctAnswer = question.correctAnswer
      || (currentSession.value.direction === 'de-fr' ? question.french : question.german)

    // Exam mode grades strictly: accents must match exactly and there is no
    // "almost correct" tolerance (a near miss is simply wrong).
    const result = checkAnswer(userAnswer, correctAnswer, { strict: isExam.value })

    // 'exact' = correct, 'close' = let user decide, 'wrong' = incorrect
    const answerRecord = {
      questionId: question.questionId || question.itemId,
      itemId: question.itemId,
      userAnswer,
      correctAnswer,
      result, // 'exact', 'close', or 'wrong'
      correct: result === 'exact', // will be updated if user accepts 'close'
      timestamp: Date.now()
    }

    answers.value.push(answerRecord)

    // Update streak based on result
    if (result === 'exact') {
      currentStreak.value++
    } else if (result === 'wrong') {
      currentStreak.value = 0
    }
    // 'close' doesn't change streak until user decides

    persistLive()
    return answerRecord
  }

  function acceptCloseAnswer() {
    const lastAnswer = answers.value[answers.value.length - 1]
    if (lastAnswer && lastAnswer.result === 'close') {
      lastAnswer.correct = true
      currentStreak.value++
    }
    persistLive()
  }

  function rejectCloseAnswer() {
    const lastAnswer = answers.value[answers.value.length - 1]
    if (lastAnswer && lastAnswer.result === 'close') {
      lastAnswer.correct = false
      currentStreak.value = 0
    }
    persistLive()
  }

  function nextQuestion() {
    if (currentQuestionIndex.value < questions.value.length - 1) {
      currentQuestionIndex.value++
      persistLive()
      return true
    }
    return false
  }

  function skipQuestion() {
    const question = currentQuestion.value
    if (!question) return

    // Track the skip so a repeatedly-dodged word can be surfaced in a focused
    // session. Deduplicated: a word skipped several times is recorded once here
    // (the server keeps its own running skipCount across sessions).
    const iid = question.itemId
    if (iid && !skippedItemIds.value.includes(iid)) {
      skippedItemIds.value.push(iid)
    }

    // Move skipped question to end of queue so it gets asked again
    questions.value.splice(currentQuestionIndex.value, 1)
    questions.value.push(question)
    // Don't increment index since the array shifted — next question is now at the same index
    persistLive()
  }

  async function endSession() {
    if (!currentSession.value) return

    const duration = Math.round((Date.now() - currentSession.value.startTime) / 1000)

    // Guard: if no answers were recorded (e.g. session abandoned right after
    // start, or local state was reset by a reload), do NOT send an empty
    // results array. An empty /practice/complete would overwrite the stored
    // score/progress with 0. Just end the session locally.
    if (!answers.value.length) {
      isSessionActive.value = false
      clearLiveSession()
      return null
    }

    const payload = {
      sessionId: currentSession.value.sessionId,
      results: answers.value.map((a) => ({
        itemId: a.itemId,
        correct: a.correct,
        userAnswer: a.userAnswer,
      })),
    }

    // Report words that were skipped and NEVER actually answered this session,
    // so the server can raise their skipCount (they keep getting dodged). Items
    // that were skipped but later answered are already covered by their answer
    // record and must not be double-counted as skips.
    const answeredItemIds = new Set(answers.value.map((a) => a.itemId))
    for (const itemId of skippedItemIds.value) {
      if (!answeredItemIds.has(itemId)) {
        payload.results.push({ itemId, correct: false, skipped: true })
      }
    }
    const localResultBase = {
      score: score.value,
      duration,
      mode: currentSession.value.mode || 'practice',
      vocabSetId: currentSession.value.vocabSetId,
      detailedResults: answers.value,
    }

    try {
      const data = await sendComplete(payload)
      sessionResults.value = {
        ...data,
        ...localResultBase,
        leagueUpdate: data.leagueUpdate || null,
        errorPatterns: data.errorPatterns || null,
      }
      savePending.value = false
      // Sent successfully → drop any buffered copies.
      removePending(payload.sessionId)
      clearLiveSession()
    } catch (err) {
      if (isNetworkError(err)) {
        // Connection died and stayed down through all retries. Do NOT pretend
        // it was saved: queue it for recovery on the next load and flag the UI.
        enqueuePending(payload)
        savePending.value = true
        sessionResults.value = { ...localResultBase, leagueUpdate: null, savePending: true }
        // Keep the live snapshot too, as a belt-and-braces backup.
      } else {
        // A genuine HTTP error (e.g. 5xx) — the server was reached. Show local
        // results; the session record/progress may still be partially stored.
        // Not queued (retrying a server error blindly is not helpful here).
        savePending.value = false
        sessionResults.value = { ...localResultBase, leagueUpdate: null }
        clearLiveSession()
      }
    }

    isSessionActive.value = false
    return sessionResults.value
  }

  /**
   * Restore an in-progress session persisted before a reload/crash/offline.
   * Returns true if a live session was restored.
   */
  function restoreLiveSession() {
    const snap = loadLiveSession()
    if (!snap || !snap.currentSession || !Array.isArray(snap.questions)) {
      return false
    }
    currentSession.value = snap.currentSession
    questions.value = snap.questions
    currentQuestionIndex.value = snap.currentQuestionIndex || 0
    answers.value = snap.answers || []
    skippedItemIds.value = snap.skippedItemIds || []
    currentStreak.value = snap.currentStreak || 0
    sessionResults.value = null
    isSessionActive.value = true
    savePending.value = false
    return true
  }

  /**
   * Re-send any completed sessions that couldn't be saved earlier (network).
   * Call on app start / when the practice area loads. Uses the pending queue in
   * practiceSync; the token layer supplies a fresh token by then.
   */
  async function recoverPendingSessions() {
    const { flushPending } = await import('@/services/practiceSync')
    return flushPending()
  }

  function resetSession() {
    currentSession.value = null
    questions.value = []
    currentQuestionIndex.value = 0
    answers.value = []
    skippedItemIds.value = []
    sessionResults.value = null
    isSessionActive.value = false
    currentStreak.value = 0
    savePending.value = false
    clearLiveSession()
  }

  return {
    currentSession,
    questions,
    currentQuestionIndex,
    answers,
    skippedItemIds,
    sessionResults,
    isSessionActive,
    currentStreak,
    savePending,
    currentQuestion,
    progress,
    score,
    mode,
    isExam,
    startSession,
    submitAnswer,
    acceptCloseAnswer,
    rejectCloseAnswer,
    nextQuestion,
    skipQuestion,
    endSession,
    resetSession,
    restoreLiveSession,
    recoverPendingSessions
  }
})
