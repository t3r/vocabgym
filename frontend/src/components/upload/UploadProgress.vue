<template>
  <div class="mt-4">
    <div class="flex items-center justify-between text-sm text-gray-600 mb-2">
      <span>Upload-Fortschritt</span>
      <span>{{ progress }}%</span>
    </div>
    <div class="w-full bg-gray-200 rounded-full h-2.5">
      <div
        class="bg-primary-600 h-2.5 rounded-full transition-all duration-300"
        :style="{ width: `${progress}%` }"
      ></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  progress: { type: Number, default: 0 }
})
</script>
