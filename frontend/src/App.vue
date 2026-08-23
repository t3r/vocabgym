<template>
  <div class="min-h-screen flex flex-col">
    <AppHeader />
    <main class="flex-1">
      <router-view />
    </main>
    <Toast />
  </div>
</template>

<script setup>
import AppHeader from '@/components/common/AppHeader.vue'
import Toast from '@/components/common/Toast.vue'
</script>
