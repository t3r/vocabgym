<template>
  <div class="flex justify-center items-center" :class="containerClass">
    <div
      class="animate-spin rounded-full border-2 border-gray-300 border-t-primary-600"
      :class="sizeClass"
      role="status"
      aria-label="Wird geladen"
    ></div>
    <span class="sr-only">Wird geladen...</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg'].includes(v)
  }
})

const sizeClass = computed(() => ({
  sm: 'w-5 h-5',
  md: 'w-8 h-8',
  lg: 'w-12 h-12'
}[props.size]))

const containerClass = computed(() => ({
  sm: 'p-2',
  md: 'p-4',
  lg: 'p-6'
}[props.size]))
</script>
