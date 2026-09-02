<template>
  <!--
    A segmented control for choosing ONE of a few equal-weight options
    (best practice for 2-4 mutually exclusive choices — clearer than a dropdown
    and semantically a radio group). Options sit side by side in a pill; the
    active one is highlighted. Fully keyboard- and screenreader-accessible.
  -->
  <div
    role="radiogroup"
    :aria-label="ariaLabel"
    class="inline-flex w-full rounded-lg bg-gray-100 dark:bg-gray-700 p-1 gap-1"
  >
    <button
      v-for="(opt, index) in options"
      :key="opt.value"
      type="button"
      role="radio"
      :aria-checked="opt.value === modelValue"
      :tabindex="opt.value === modelValue ? 0 : -1"
      @click="select(opt.value)"
      @keydown="onKeydown($event, index)"
      class="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 dark:focus:ring-offset-gray-700"
      :class="opt.value === modelValue
        ? 'bg-white dark:bg-gray-900 text-primary-700 dark:text-primary-300 shadow-sm'
        : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'"
    >
      <span v-if="opt.icon" aria-hidden="true">{{ opt.icon }}</span>
      <span>{{ opt.label }}</span>
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  // The currently selected value (v-model).
  modelValue: { type: [String, Number, Boolean], required: true },
  // [{ value, label, icon? }]
  options: { type: Array, required: true },
  ariaLabel: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

function select(value) {
  if (value !== props.modelValue) emit('update:modelValue', value)
}

// Arrow-key navigation between segments (standard radiogroup behaviour).
function onKeydown(event, index) {
  const { key } = event
  const last = props.options.length - 1
  let target = null

  if (key === 'ArrowRight' || key === 'ArrowDown') {
    target = index === last ? 0 : index + 1
  } else if (key === 'ArrowLeft' || key === 'ArrowUp') {
    target = index === 0 ? last : index - 1
  } else {
    return
  }

  event.preventDefault()
  const opt = props.options[target]
  select(opt.value)
  // Move focus to the newly selected segment.
  const buttons = event.currentTarget.parentElement.querySelectorAll('[role="radio"]')
  buttons[target]?.focus()
}
</script>
