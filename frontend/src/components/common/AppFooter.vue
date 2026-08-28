<template>
  <footer class="mt-auto border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row items-center justify-between gap-2">
      <p class="text-xs text-gray-500 dark:text-gray-400">
        © {{ year }} VocabGym
      </p>
      <nav class="flex items-center gap-4 text-xs">
        <router-link
          to="/datenschutz"
          class="text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400"
        >
          Datenschutz
        </router-link>
        <router-link
          to="/impressum"
          class="text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400"
        >
          Impressum
        </router-link>
        <router-link
          to="/help"
          class="text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400"
        >
          Hilfe
        </router-link>
      </nav>
    </div>
  </footer>
</template>

<script setup>
const year = new Date().getFullYear()
</script>
