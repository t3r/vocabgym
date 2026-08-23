<template>
  <div class="card">
    <h3 class="font-semibold text-gray-900 mb-4">Metadaten</h3>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label class="label">Titel</label>
        <input
          :value="title"
          @input="$emit('update:title', $event.target.value)"
          class="input-field"
          placeholder="z.B. Kapitel 3: Zuhause"
        />
      </div>
      <div>
        <label class="label">Kapitel</label>
        <input
          :value="chapter"
          @input="$emit('update:chapter', $event.target.value)"
          class="input-field"
          placeholder="z.B. 3"
        />
      </div>
      <div>
        <label class="label">Seite</label>
        <input
          :value="pageNumber"
          @input="$emit('update:pageNumber', $event.target.value)"
          type="number"
          class="input-field"
          placeholder="z.B. 42"
          min="1"
        />
      </div>
      <div>
        <label class="label">Thema</label>
        <input
          :value="topic"
          @input="$emit('update:topic', $event.target.value)"
          class="input-field"
          placeholder="z.B. Familie"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  chapter: { type: String, default: '' },
  pageNumber: { type: [String, Number], default: '' },
  topic: { type: String, default: '' }
})

defineEmits(['update:title', 'update:chapter', 'update:pageNumber', 'update:topic'])
</script>
