<template>
  <div>
    <div class="flex items-center justify-between text-sm text-gray-600 mb-2">
      <span>Frage {{ current }} von {{ total }}</span>
      <span>{{ percentage }}%</span>
    </div>
    <div class="w-full bg-gray-200 rounded-full h-2">
      <div
        class="bg-primary-600 h-2 rounded-full transition-all duration-300"
        :style="{ width: `${percentage}%` }"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  current: { type: Number, required: true },
  total: { type: Number, required: true }
})

const percentage = computed(() => {
  if (!props.total) return 0
  return Math.round((props.current / props.total) * 100)
})
</script>
