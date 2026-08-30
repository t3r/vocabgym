import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePracticeStore } from '@/stores/practice'

describe('practice store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePracticeStore()
  })

  // Helper to set up a minimal session with questions
  function setupSession(questionsList) {
    store.currentSession = {
      sessionId: 'test-session',
      vocabSetId: 'test-set',
      direction: 'de-fr',
      startTime: Date.now(),
    }
    store.questions = questionsList
    store.currentQuestionIndex = 0
    store.answers = []
    store.isSessionActive = true
    store.currentStreak = 0
  }

  const sampleQuestions = [
    { questionId: 'q1', itemId: 'i1', question: 'das Haus', correctAnswer: 'la maison' },
    { questionId: 'q2', itemId: 'i2', question: 'die Schule', correctAnswer: "l'école" },
    { questionId: 'q3', itemId: 'i3', question: 'die Katze', correctAnswer: 'le chat' },
  ]

  describe('exam mode getters', () => {
    it('defaults to practice mode when no session', () => {
      expect(store.mode).toBe('practice')
      expect(store.isExam).toBe(false)
    })

    it('reflects exam mode from currentSession', () => {
      store.currentSession = {
        sessionId: 's', vocabSetId: 'vs', direction: 'de-fr', mode: 'exam', startTime: Date.now(),
      }
      expect(store.mode).toBe('exam')
      expect(store.isExam).toBe(true)
    })

    it('reflects practice mode from currentSession', () => {
      store.currentSession = {
        sessionId: 's', vocabSetId: 'vs', direction: 'de-fr', mode: 'practice', startTime: Date.now(),
      }
      expect(store.isExam).toBe(false)
    })
  })

  describe('initial state', () => {
    it('starts with no session', () => {
      expect(store.currentSession).toBeNull()
      expect(store.questions).toEqual([])
      expect(store.currentQuestionIndex).toBe(0)
      expect(store.answers).toEqual([])
      expect(store.isSessionActive).toBe(false)
      expect(store.currentStreak).toBe(0)
    })

    it('currentQuestion is null when no questions', () => {
      expect(store.currentQuestion).toBeNull()
    })

    it('score starts at zero', () => {
      expect(store.score).toEqual({ correct: 0, total: 0, percentage: 0 })
    })
  })

  describe('submitAnswer', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('returns exact for a correct answer', () => {
      const result = store.submitAnswer('la maison')
      expect(result.result).toBe('exact')
      expect(result.correct).toBe(true)
    })

    it('returns close for a near-miss answer', () => {
      const result = store.submitAnswer('la maisom')
      expect(result.result).toBe('close')
      // 'close' is not marked as correct yet (user must accept)
      expect(result.correct).toBe(false)
    })

    it('returns wrong for a completely wrong answer', () => {
      const result = store.submitAnswer('le chat')
      expect(result.result).toBe('wrong')
      expect(result.correct).toBe(false)
    })

    it('pushes answer record into answers array', () => {
      store.submitAnswer('la maison')
      expect(store.answers).toHaveLength(1)
      expect(store.answers[0].userAnswer).toBe('la maison')
      expect(store.answers[0].correctAnswer).toBe('la maison')
      expect(store.answers[0].itemId).toBe('i1')
    })

    it('returns null when there is no current question', () => {
      store.currentQuestionIndex = 999
      const result = store.submitAnswer('something')
      expect(result).toBeNull()
    })
  })

  describe('streak tracking', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('increments streak on exact answer', () => {
      store.submitAnswer('la maison')
      expect(store.currentStreak).toBe(1)
    })

    it('resets streak on wrong answer', () => {
      store.submitAnswer('la maison') // correct → streak = 1
      store.nextQuestion()
      store.submitAnswer('completely wrong') // wrong → streak = 0
      expect(store.currentStreak).toBe(0)
    })

    it('does not change streak on close answer before user decides', () => {
      store.submitAnswer('la maisom') // close
      expect(store.currentStreak).toBe(0) // unchanged from initial
    })

    it('increments streak when user accepts close answer', () => {
      store.submitAnswer('la maisom') // close
      store.acceptCloseAnswer()
      expect(store.currentStreak).toBe(1)
    })

    it('resets streak when user rejects close answer', () => {
      // First get a correct answer to build streak
      store.submitAnswer('la maison') // exact → streak = 1
      store.nextQuestion()
      store.submitAnswer('lecolx') // close match for l'école (off by one char after normalization)
      expect(store.answers[store.answers.length - 1].result).toBe('close')
      store.rejectCloseAnswer()
      expect(store.currentStreak).toBe(0)
    })

    it('accumulates streak over multiple correct answers', () => {
      store.submitAnswer('la maison') // exact → streak = 1
      store.nextQuestion()
      store.submitAnswer("l'école") // exact → streak = 2
      store.nextQuestion()
      store.submitAnswer('le chat') // exact → streak = 3
      expect(store.currentStreak).toBe(3)
    })
  })

  describe('acceptCloseAnswer', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('marks last close answer as correct', () => {
      store.submitAnswer('la maisom') // close
      expect(store.answers[0].correct).toBe(false)
      store.acceptCloseAnswer()
      expect(store.answers[0].correct).toBe(true)
    })

    it('does nothing if last answer is not close', () => {
      store.submitAnswer('la maison') // exact
      const correctBefore = store.answers[0].correct
      store.acceptCloseAnswer()
      expect(store.answers[0].correct).toBe(correctBefore)
    })
  })

  describe('rejectCloseAnswer', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('marks last close answer as incorrect', () => {
      store.submitAnswer('la maisom') // close
      store.rejectCloseAnswer()
      expect(store.answers[0].correct).toBe(false)
    })

    it('resets streak to 0', () => {
      store.submitAnswer('la maison') // exact → streak = 1
      store.nextQuestion()
      store.submitAnswer('lecolx') // close match for l'école
      expect(store.answers[store.answers.length - 1].result).toBe('close')
      store.rejectCloseAnswer()
      expect(store.currentStreak).toBe(0)
    })
  })

  describe('nextQuestion', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('advances to next question', () => {
      expect(store.currentQuestionIndex).toBe(0)
      const hasNext = store.nextQuestion()
      expect(hasNext).toBe(true)
      expect(store.currentQuestionIndex).toBe(1)
    })

    it('returns false at the last question', () => {
      store.currentQuestionIndex = 2 // last question
      const hasNext = store.nextQuestion()
      expect(hasNext).toBe(false)
      expect(store.currentQuestionIndex).toBe(2) // unchanged
    })

    it('currentQuestion updates after advancing', () => {
      expect(store.currentQuestion.questionId).toBe('q1')
      store.nextQuestion()
      expect(store.currentQuestion.questionId).toBe('q2')
    })
  })

  describe('skipQuestion', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('moves current question to the end of the queue', () => {
      expect(store.questions[0].questionId).toBe('q1')
      store.skipQuestion()
      // q1 moved to end, so now q2 is first
      expect(store.questions[0].questionId).toBe('q2')
      expect(store.questions[store.questions.length - 1].questionId).toBe('q1')
    })

    it('keeps total question count the same', () => {
      const countBefore = store.questions.length
      store.skipQuestion()
      expect(store.questions.length).toBe(countBefore)
    })

    it('current index stays the same (next question slides into position)', () => {
      store.skipQuestion()
      expect(store.currentQuestionIndex).toBe(0)
      // The new question at index 0 is now q2
      expect(store.currentQuestion.questionId).toBe('q2')
    })
  })

  describe('score computed', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('calculates score after one correct answer', () => {
      store.submitAnswer('la maison') // exact
      expect(store.score).toEqual({ correct: 1, total: 1, percentage: 100 })
    })

    it('calculates score after mixed answers', () => {
      store.submitAnswer('la maison') // exact/correct
      store.nextQuestion()
      store.submitAnswer('completely wrong') // wrong
      expect(store.score).toEqual({ correct: 1, total: 2, percentage: 50 })
    })

    it('updates score when close answer is accepted', () => {
      store.submitAnswer('la maisom') // close, initially not correct
      expect(store.score.correct).toBe(0)
      store.acceptCloseAnswer()
      expect(store.score.correct).toBe(1)
    })
  })

  describe('progress computed', () => {
    beforeEach(() => {
      setupSession([...sampleQuestions])
    })

    it('starts at question 1 of total', () => {
      expect(store.progress).toEqual({ current: 1, total: 3, percentage: 33 })
    })

    it('updates as questions advance', () => {
      store.nextQuestion()
      expect(store.progress.current).toBe(2)
      expect(store.progress.percentage).toBe(67)
    })
  })

  describe('resetSession', () => {
    it('clears all session state', () => {
      setupSession([...sampleQuestions])
      store.submitAnswer('la maison')
      store.currentStreak = 5

      store.resetSession()

      expect(store.currentSession).toBeNull()
      expect(store.questions).toEqual([])
      expect(store.currentQuestionIndex).toBe(0)
      expect(store.answers).toEqual([])
      expect(store.sessionResults).toBeNull()
      expect(store.isSessionActive).toBe(false)
      expect(store.currentStreak).toBe(0)
    })
  })
})
