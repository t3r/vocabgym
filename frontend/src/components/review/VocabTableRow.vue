<template>
  <tr class="border-b border-gray-100 group">
    <td class="py-2 text-sm text-gray-400 align-middle">{{ index + 1 }}</td>
    <td class="py-2 pr-2">
      <input
        :value="item.source || item.german"
        @input="$emit('update', 'source', $event.target.value)"
        class="input-field text-sm"
        :class="{ 'border-error': !(item.source || item.german)?.trim() }"
        placeholder="Deutsch"
      />
    </td>
    <td class="py-2 pr-2">
      <input
        :value="item.target || item.french"
        @input="$emit('update', 'target', $event.target.value)"
        class="input-field text-sm"
        :class="{ 'border-error': !(item.target || item.french)?.trim() }"
        :placeholder="getLanguageName(targetLanguage)"
      />
    </td>
    <td class="py-2 text-center">
      <button
        @click="$emit('delete')"
        class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-error transition-all p-1 rounded"
        aria-label="Zeile löschen"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </td>
  </tr>
</template>

<script setup>
import { getLanguageName } from '@/utils/languages'

defineProps({
  item: { type: Object, required: true },
  index: { type: Number, required: true },
  targetLanguage: { type: String, default: 'fr' }
})

defineEmits(['update', 'delete'])
</script>
