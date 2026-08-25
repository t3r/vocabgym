<template>
  <div class="overflow-x-auto">
    <table class="w-full">
      <thead>
        <tr class="border-b border-gray-200 dark:border-gray-700">
          <th class="pb-2 text-left text-sm font-medium text-gray-500 w-8">#</th>
          <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">Deutsch</th>
          <th class="pb-2 text-left text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">Französisch</th>
          <th class="pb-2 w-10"></th>
        </tr>
      </thead>
      <tbody>
        <VocabTableRow
          v-for="(item, index) in items"
          :key="item.itemId"
          :item="item"
          :index="index"
          @update="(field, value) => $emit('update', index, field, value)"
          @delete="$emit('delete', index)"
        />
      </tbody>
    </table>

    <!-- Add Row Button -->
    <button
      @click="$emit('add')"
      class="mt-4 w-full py-2 border-2 border-dashed border-gray-300 rounded-md text-sm text-gray-500 hover:border-primary-400 hover:text-primary-600 transition-colors"
    >
      + Zeile hinzufügen
    </button>
  </div>
</template>

<script setup>
import VocabTableRow from './VocabTableRow.vue'

defineProps({
  items: { type: Array, required: true }
})

defineEmits(['update', 'delete', 'add'])
</script>
