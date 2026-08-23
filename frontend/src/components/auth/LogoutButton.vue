<template>
  <button @click="logout" class="btn-secondary text-sm">
    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
    Abmelden
  </button>
</template>

<script setup>
import { useAuth } from '@/composables/useAuth'

const { logout } = useAuth()
</script>
