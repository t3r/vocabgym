/**
 * Formatting utilities for display.
 */

/**
 * Format a Unix timestamp or Date to a locale date string
 */
export function formatDate(timestamp, options = {}) {
  if (!timestamp) return '—'

  const date = typeof timestamp === 'number'
    ? new Date(timestamp < 1e12 ? timestamp * 1000 : timestamp)
    : new Date(timestamp)

  const defaultOptions = {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...options
  }

  return date.toLocaleDateString('de-DE', defaultOptions)
}

/**
 * Format a duration in seconds to a human-readable string
 */
export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0 Sek.'

  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60

  if (minutes === 0) {
    return `${remainingSeconds} Sek.`
  }

  if (remainingSeconds === 0) {
    return `${minutes} Min.`
  }

  return `${minutes} Min. ${remainingSeconds} Sek.`
}

/**
 * Format a number as a percentage string
 */
export function formatPercentage(value, decimals = 0) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(decimals)}%`
}

/**
 * Format a practice score (e.g., "18/20")
 */
export function formatScore(correct, total) {
  if (total === 0) return '—'
  return `${correct}/${total}`
}

/**
 * Format a relative time (e.g., "vor 2 Stunden")
 */
export function formatRelativeTime(timestamp) {
  if (!timestamp) return '—'

  const date = typeof timestamp === 'number'
    ? new Date(timestamp < 1e12 ? timestamp * 1000 : timestamp)
    : new Date(timestamp)

  const now = new Date()
  const diffMs = now - date
  const diffMinutes = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMinutes < 1) return 'gerade eben'
  if (diffMinutes < 60) return `vor ${diffMinutes} Min.`
  if (diffHours < 24) return `vor ${diffHours} Std.`
  if (diffDays < 7) return `vor ${diffDays} Tagen`

  return formatDate(timestamp)
}
