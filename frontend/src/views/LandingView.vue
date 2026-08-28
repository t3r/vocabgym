<template>
  <!-- Landing page: Hero section, feature highlights, and login CTA -->
  <div class="min-h-screen">
    <!-- Hero Section -->
    <section class="relative bg-gradient-to-br from-primary-600 to-primary-800 text-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 sm:py-32">
        <div class="text-center">
          <h1 class="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight">
            Vokabeln lernen — Französisch, Englisch, Spanisch, Italienisch
          </h1>
          <p class="mt-6 text-lg sm:text-xl text-primary-100 max-w-2xl mx-auto">
            Scanne deine Arbeitsbuchseiten, extrahiere Vokabeln automatisch und übe mit
            interaktiven Übungen. Perfekt für die 9. Klasse.
          </p>
          <div class="mt-10">
            <LoginButton size="lg" />
          </div>
        </div>
      </div>
    </section>

    <!-- Features Section -->
    <section class="py-20 bg-white dark:bg-gray-900">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="text-3xl font-bold text-center text-gray-900 dark:text-white mb-12">
          So einfach geht's
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <!-- Feature 1: Scan -->
          <div class="text-center p-6">
            <div class="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg class="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold mb-2 text-gray-900 dark:text-white">Scannen</h3>
            <p class="text-gray-600 dark:text-gray-300">
              Fotografiere einfach die Vokabeltabelle aus deinem Arbeitsbuch.
            </p>
          </div>

          <!-- Feature 2: Review -->
          <div class="text-center p-6">
            <div class="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg class="w-8 h-8 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold mb-2 text-gray-900 dark:text-white">Prüfen</h3>
            <p class="text-gray-600 dark:text-gray-300">
              Die KI erkennt die Vokabeln automatisch. Du kannst sie noch bearbeiten.
            </p>
          </div>

          <!-- Feature 3: Practice -->
          <div class="text-center p-6">
            <div class="w-16 h-16 bg-warning/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg class="w-8 h-8 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold mb-2 text-gray-900 dark:text-white">Üben</h3>
            <p class="text-gray-600 dark:text-gray-300">
              Trainiere mit interaktiven Übungen und verfolge deinen Fortschritt.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="py-16 bg-gray-50 dark:bg-gray-800">
      <div class="max-w-4xl mx-auto text-center px-4">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          Bereit loszulegen?
        </h2>
        <p class="text-gray-600 dark:text-gray-300 mb-8">
          Erstelle jetzt dein kostenloses Konto und beginne sofort mit dem Lernen.
        </p>
        <LoginButton />
      </div>
    </section>
  </div>
</template>

<script setup>
import LoginButton from '@/components/auth/LoginButton.vue'
</script>
