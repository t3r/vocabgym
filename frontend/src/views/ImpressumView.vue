<template>
  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">Impressum</h1>

    <div v-if="isLoading" class="text-gray-500 dark:text-gray-400">Wird geladen…</div>

    <div
      v-else-if="html"
      class="legal-content"
      v-html="html"
    ></div>

    <div v-else class="text-gray-600 dark:text-gray-300 space-y-3">
      <p>Das Impressum ist derzeit nicht verfügbar.</p>
      <p class="text-sm text-gray-500 dark:text-gray-400">
        Bitte wenden Sie sich an den Betreiber dieser Anwendung.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const html = ref('')
const isLoading = ref(true)

const DOC_URL = '/legal/impressum.de.html'

onMounted(async () => {
  try {
    const res = await fetch(DOC_URL, { headers: { Accept: 'text/html' } })
    const text = res.ok ? await res.text() : ''
    if (text && !text.includes('<div id="app">')) {
      html.value = text
    }
  } catch {
    // leave html empty -> fallback message
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
.legal-content {
  @apply text-gray-700 dark:text-gray-300 leading-relaxed;
}
.legal-content :deep(h2) {
  @apply text-lg font-semibold text-gray-900 dark:text-white mb-2 mt-6;
}
.legal-content :deep(p) {
  @apply mb-2;
}
.legal-content :deep(a) {
  @apply text-primary-600 dark:text-primary-400 underline;
}
</style>
