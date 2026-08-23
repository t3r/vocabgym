import { defineStore } from 'pinia'
import { ref } from 'vue'

let toastId = 0

export const useUiStore = defineStore('ui', () => {
  const toasts = ref([])
  const modal = ref({ isOpen: false, component: null, props: {} })
  const sidebarOpen = ref(false)

  function showToast(message, type = 'info', duration = 4000) {
    const id = ++toastId
    const toast = { id, message, type, duration }
    toasts.value.push(toast)

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }

    return id
  }

  function removeToast(id) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function openModal(component, props = {}) {
    modal.value = { isOpen: true, component, props }
  }

  function closeModal() {
    modal.value = { isOpen: false, component: null, props: {} }
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  return {
    toasts,
    modal,
    sidebarOpen,
    showToast,
    removeToast,
    openModal,
    closeModal,
    toggleSidebar
  }
})
