<template>
  <div>
    <h3 class="font-semibold text-gray-900 mb-3">Originalbild</h3>
    <div v-if="imageUrl" class="rounded-lg overflow-hidden border border-gray-200">
      <img
        :src="imageUrl"
        alt="Arbeitsbuchseite"
        class="w-full h-auto"
        loading="lazy"
      />
    </div>
    <div v-else class="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
      <p class="text-gray-400 text-sm">Kein Bild verfügbar</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  imageUrl: { type: String, default: null },
  imageKey: { type: String, default: null }
})
</script>
