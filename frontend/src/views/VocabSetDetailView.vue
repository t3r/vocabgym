<template>
  <!-- Vocab Set Detail: Full vocabulary list, practice/edit actions, stats -->
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <LoadingSpinner v-if="isLoading" class="py-12" />

    <template v-else-if="vocabSet">
      <!-- Header -->
      <div class="mb-6 flex items-start justify-between">
        <div>
          <router-link to="/dashboard" class="text-sm text-primary-600 hover:text-primary-700 mb-2 inline-block">
            ← Zurück zum Dashboard
          </router-link>
          <h1 class="text-2xl font-bold text-gray-900">{{ vocabSet.title || 'Unbenanntes Set' }}</h1>
          <p class="text-gray-600 mt-1">
            {{ vocabSet.itemCount || items.length }} Vokabeln
            <span v-if="vocabSet.metadata?.chapter"> · Kapitel {{ vocabSet.metadata.chapter }}</span>
            <span v-if="vocabSet.metadata?.topic"> · {{ vocabSet.metadata.topic }}</span>
          </p>
        </div>
        <div class="flex gap-2">
          <router-link
            :to="{ name: 'Review', params: { vocabSetId } }"
            class="btn-secondary"
          >
            Bearbeiten
          </router-link>
          <router-link
            :to="{ name: 'Practice', params: { vocabSetId } }"
            class="btn-primary"
          >
            Üben
          </router-link>
        </div>
      </div>

      <!-- Stats Overview -->
      <div class="card mb-6">
        <div class="flex items-center justify-between">
          <h3 class="font-semibold text-gray-900">Überblick</h3>
          <span class="text-sm text-gray-500">{{ items.length }} Vokabeln</span>
        </div>
      </div>

      <!-- Vocabulary Table (read-only) -->
      <div class="card">
        <h3 class="font-semibold text-gray-900 mb-4">Vokabeln</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-left">
            <thead>
              <tr class="border-b border-gray-200">
                <th class="pb-3 text-sm font-medium text-gray-500">#</th>
                <th class="pb-3 text-sm font-medium text-gray-500">Deutsch</th>
                <th class="pb-3 text-sm font-medium text-gray-500">Französisch</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in items" :key="item.itemId" class="border-b border-gray-100">
                <td class="py-3 text-sm text-gray-400">{{ index + 1 }}</td>
                <td class="py-3 font-medium">{{ item.german }}</td>
                <td class="py-3">{{ item.french }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <div v-else class="card text-center py-12">
      <p class="text-gray-600">Vokabelset nicht gefunden.</p>
      <router-link to="/dashboard" class="btn-primary mt-4">Zum Dashboard</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useVocabStore } from '@/stores/vocab'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const props = defineProps({
  vocabSetId: { type: String, required: true }
})

const vocabStore = useVocabStore()
const isLoading = ref(true)
const vocabSet = ref(null)
const items = ref([])

onMounted(async () => {
  try {
    const data = await vocabStore.fetchVocabSet(props.vocabSetId)
    vocabSet.value = data
    items.value = data.items || []
  } catch {
    // Error handled by store
  } finally {
    isLoading.value = false
  }
})
</script>
