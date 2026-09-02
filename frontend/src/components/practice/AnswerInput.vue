<template>
  <form @submit.prevent="handleSubmit" class="flex gap-3">
    <input
      ref="inputRef"
      v-model="answer"
      type="text"
      :placeholder="placeholder"
      class="input-field text-lg flex-1"
      autocomplete="off"
      autocorrect="off"
      autocapitalize="off"
      spellcheck="false"
      inputmode="text"
      enterkeyhint="done"
    />
    <button
      type="submit"
      class="btn-primary"
      :disabled="!answer.trim()"
    >
      Prüfen
    </button>
  </form>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  placeholder: { type: String, default: 'Antwort eingeben...' }
})

const emit = defineEmits(['submit'])

const answer = ref('')
const inputRef = ref(null)

function handleSubmit() {
  if (!answer.value.trim()) return
  emit('submit', answer.value.trim())
  answer.value = ''
}

onMounted(() => {
  inputRef.value?.focus()
})
</script>
