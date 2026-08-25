<template>
  <Teleport to="body">
    <transition name="modal">
      <div v-if="isOpen" class="fixed inset-0 z-50 overflow-y-auto">
        <!-- Backdrop -->
        <div
          class="fixed inset-0 bg-black/50 transition-opacity"
          @click="handleBackdropClick"
        ></div>

        <!-- Modal Panel -->
        <div class="flex min-h-full items-center justify-center p-4">
          <div
            class="relative bg-white rounded-lg shadow-xl w-full transform transition-all"
            :class="sizeClass"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="titleId"
          >
            <!-- Header -->
            <div v-if="title || $slots.header" class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <slot name="header">
                <h3 :id="titleId" class="text-lg font-semibold text-gray-900 dark:text-white">{{ title }}</h3>
              </slot>
              <button
                v-if="closeable"
                @click="$emit('close')"
                class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:text-gray-300"
                aria-label="Schließen"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Body -->
            <div class="px-6 py-4">
              <slot></slot>
            </div>

            <!-- Footer -->
            <div v-if="$slots.footer" class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <slot name="footer"></slot>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  title: { type: String, default: '' },
  size: { type: String, default: 'md', validator: (v) => ['sm', 'md', 'lg', 'xl'].includes(v) },
  closeable: { type: Boolean, default: true },
  closeOnBackdrop: { type: Boolean, default: true }
})

const emit = defineEmits(['close'])

const titleId = computed(() => `modal-title-${Math.random().toString(36).slice(2)}`)

const sizeClass = computed(() => ({
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl'
}[props.size]))

function handleBackdropClick() {
  if (props.closeOnBackdrop) {
    emit('close')
  }
}

function handleEscape(e) {
  if (e.key === 'Escape' && props.isOpen && props.closeable) {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEscape)
})
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
