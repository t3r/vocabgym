<template>
  <div class="flex items-center gap-2">
    <div class="flex gap-0.5">
      <div
        v-for="i in 5"
        :key="i"
        class="w-3 h-3 rounded-sm"
        :class="i <= filledBars ? activeColor : 'bg-gray-200'"
      ></div>
    </div>
    <span class="text-xs text-gray-500 dark:text-gray-400 dark:text-gray-500">{{ label }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  level: { type: Number, default: 0 } // 0-100 percentage or 0-5 level
})

const filledBars = computed(() => {
  if (props.level > 5) {
    // Percentage mode: convert to 0-5
    return Math.round(props.level / 20)
  }
  return Math.round(props.level)
})

const activeColor = computed(() => {
  if (filledBars.value >= 4) return 'bg-success'
  if (filledBars.value >= 2) return 'bg-warning'
  return 'bg-error'
})

const label = computed(() => {
  const labels = ['Neu', 'Anfänger', 'Lernend', 'Vertraut', 'Gut', 'Beherrscht']
  return labels[filledBars.value] || 'Neu'
})
</script>
