import { useUiStore } from '@/stores/ui'

/**
 * Composable for showing toast notifications.
 */
export function useToast() {
  const uiStore = useUiStore()

  function showSuccess(message, duration = 4000) {
    return uiStore.showToast(message, 'success', duration)
  }

  function showError(message, duration = 8000) {
    return uiStore.showToast(message, 'error', duration)
  }

  function showInfo(message, duration = 4000) {
    return uiStore.showToast(message, 'info', duration)
  }

  function showWarning(message, duration = 5000) {
    return uiStore.showToast(message, 'warning', duration)
  }

  /**
   * Show an error from an API response, including error ID if available.
   */
  function showApiError(err, fallbackMessage = 'Ein Fehler ist aufgetreten.') {
    const data = err?.response?.data
    let message = fallbackMessage

    if (data) {
      if (data.errorId) {
        message = `${data.error || fallbackMessage} (Fehler-ID: ${data.errorId})`
      } else if (data.error) {
        message = data.error
      } else if (data.message) {
        message = data.message
      }
    } else if (err?.message) {
      message = err.message
    }

    return uiStore.showToast(message, 'error', 10000)
  }

  function dismiss(id) {
    uiStore.removeToast(id)
  }

  return {
    showSuccess,
    showError,
    showInfo,
    showWarning,
    showApiError,
    dismiss
  }
}
