import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

export const useVocabStore = defineStore('vocab', () => {
  const vocabSets = ref([])
  const currentVocabSet = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  const sortedVocabSets = computed(() => {
    return [...vocabSets.value].sort((a, b) => b.createdAt - a.createdAt)
  })

  const vocabSetById = computed(() => {
    return (id) => vocabSets.value.find((set) => set.vocabSetId === id)
  })

  async function fetchVocabSets() {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.get('/vocab')
      vocabSets.value = response.data.vocabSets || response.data || []
    } catch (err) {
      error.value = err.response?.data?.message || 'Fehler beim Laden der Vokabelsets'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchVocabSet(vocabSetId) {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.get(`/vocab/${vocabSetId}`)
      currentVocabSet.value = response.data
      return response.data
    } catch (err) {
      error.value = err.response?.data?.message || 'Fehler beim Laden des Vokabelsets'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function createVocabSet(data) {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.post('/vocab', data)
      const newSet = response.data
      vocabSets.value.push(newSet)
      return newSet
    } catch (err) {
      error.value = err.response?.data?.message || 'Fehler beim Erstellen des Vokabelsets'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function updateVocabSet(vocabSetId, data) {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.put(`/vocab/${vocabSetId}`, data)
      const updated = response.data

      const index = vocabSets.value.findIndex((s) => s.vocabSetId === vocabSetId)
      if (index !== -1) {
        vocabSets.value[index] = { ...vocabSets.value[index], ...updated }
      }

      if (currentVocabSet.value?.vocabSetId === vocabSetId) {
        currentVocabSet.value = { ...currentVocabSet.value, ...updated }
      }

      return updated
    } catch (err) {
      error.value = err.response?.data?.message || 'Fehler beim Aktualisieren des Vokabelsets'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function deleteVocabSet(vocabSetId) {
    isLoading.value = true
    error.value = null
    try {
      await api.delete(`/vocab/${vocabSetId}`)
      vocabSets.value = vocabSets.value.filter((s) => s.vocabSetId !== vocabSetId)

      if (currentVocabSet.value?.vocabSetId === vocabSetId) {
        currentVocabSet.value = null
      }
    } catch (err) {
      error.value = err.response?.data?.message || 'Fehler beim Löschen des Vokabelsets'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    vocabSets,
    currentVocabSet,
    isLoading,
    error,
    sortedVocabSets,
    vocabSetById,
    fetchVocabSets,
    fetchVocabSet,
    createVocabSet,
    updateVocabSet,
    deleteVocabSet
  }
})
