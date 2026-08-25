<template>
  <!-- 404 Not Found Page -->
  <div class="min-h-[60vh] flex items-center justify-center px-4">
    <div class="text-center">
      <p class="text-6xl font-bold text-primary-600 mb-4">404</p>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Seite nicht gefunden</h1>
      <p class="text-gray-600 mb-8">
        Die angeforderte Seite existiert leider nicht.
      </p>
      <router-link to="/" class="btn-primary">Zur Startseite</router-link>
    </div>
  </div>
</template>
