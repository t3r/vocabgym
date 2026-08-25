import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { checkAnswer } from '@/utils/fuzzyMatch'

export const usePracticeStore = defineStore('practice', () => {
  const currentSession = ref(null)
  const questions = ref([])
  const currentQuestionIndex = ref(0)
  const answers = ref([])
  const sessionResults = ref(null)
  const isSessionActive = ref(false)
  const currentStreak = ref(0)

  const currentQuestion = computed(() => {
    if (!questions.value.length || currentQuestionIndex.value >= questions.value.length) {
      return null
    }
    return questions.value[currentQuestionIndex.value]
  })

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
        questionCount: options.questionCount || 20
      })

      currentSession.value = {
        sessionId: response.data.sessionId,
        vocabSetId,
        direction: options.direction || 'de-fr',
        startTime: Date.now()
      }
      // Clean correctAnswer: strip phonetic transcriptions in brackets
      questions.value = (response.data.questions || []).map(q => ({
        ...q,
        correctAnswer: q.correctAnswer
          ? q.correctAnswer.replace(/\[.*$/g, '').replace(/\(.*$/g, '').trim()
          : q.correctAnswer
      }))
      currentQuestionIndex.value = 0
      answers.value = []
      sessionResults.value = null
      isSessionActive.value = true

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

    const result = checkAnswer(userAnswer, correctAnswer)

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

    return answerRecord
  }

  function acceptCloseAnswer() {
    const lastAnswer = answers.value[answers.value.length - 1]
    if (lastAnswer && lastAnswer.result === 'close') {
      lastAnswer.correct = true
      currentStreak.value++
    }
  }

  function rejectCloseAnswer() {
    const lastAnswer = answers.value[answers.value.length - 1]
    if (lastAnswer && lastAnswer.result === 'close') {
      lastAnswer.correct = false
      currentStreak.value = 0
    }
  }

  function nextQuestion() {
    if (currentQuestionIndex.value < questions.value.length - 1) {
      currentQuestionIndex.value++
      return true
    }
    return false
  }

  function skipQuestion() {
    const question = currentQuestion.value
    if (!question) return

    // Move skipped question to end of queue so it gets asked again
    questions.value.splice(currentQuestionIndex.value, 1)
    questions.value.push(question)
    // Don't increment index since the array shifted — next question is now at the same index
  }

  async function endSession() {
    if (!currentSession.value) return

    const duration = Math.round((Date.now() - currentSession.value.startTime) / 1000)

    try {
      const response = await api.post('/practice/complete', {
        sessionId: currentSession.value.sessionId,
        results: answers.value.map((a) => ({
          itemId: a.itemId,
          correct: a.correct,
          userAnswer: a.userAnswer
        }))
      })

      sessionResults.value = {
        ...response.data,
        score: score.value,
        duration,
        detailedResults: answers.value,
        leagueUpdate: response.data.leagueUpdate || null
      }
    } catch {
      // Even if API fails, show local results
      sessionResults.value = {
        score: score.value,
        duration,
        detailedResults: answers.value,
        leagueUpdate: null
      }
    }

    isSessionActive.value = false
    return sessionResults.value
  }

  function resetSession() {
    currentSession.value = null
    questions.value = []
    currentQuestionIndex.value = 0
    answers.value = []
    sessionResults.value = null
    isSessionActive.value = false
    currentStreak.value = 0
  }

  return {
    currentSession,
    questions,
    currentQuestionIndex,
    answers,
    sessionResults,
    isSessionActive,
    currentStreak,
    currentQuestion,
    progress,
    score,
    startSession,
    submitAnswer,
    acceptCloseAnswer,
    rejectCloseAnswer,
    nextQuestion,
    skipQuestion,
    endSession,
    resetSession
  }
})
