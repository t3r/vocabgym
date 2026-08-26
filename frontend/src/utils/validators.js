/**
 * Form validation utilities.
 */

export function required(value) {
  if (value === null || value === undefined || value === '') {
    return 'Dieses Feld ist erforderlich'
  }
  return true
}

export function maxLength(max) {
  return (value) => {
    if (!value) return true
    if (value.length > max) {
      return `Maximal ${max} Zeichen erlaubt`
    }
    return true
  }
}

export function minLength(min) {
  return (value) => {
    if (!value) return true
    if (value.length < min) {
      return `Mindestens ${min} Zeichen erforderlich`
    }
    return true
  }
}

export function isPositiveInteger(value) {
  if (!value) return true
  const num = Number(value)
  if (!Number.isInteger(num) || num <= 0) {
    return 'Muss eine positive Ganzzahl sein'
  }
  return true
}

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png']

export function isValidFileType(file) {
  if (!file) return true
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return 'Nur JPG und PNG Dateien sind erlaubt'
  }
  return true
}

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

export function isValidFileSize(file, maxSize = MAX_FILE_SIZE) {
  if (!file) return true
  if (file.size > maxSize) {
    const maxMB = Math.round(maxSize / 1024 / 1024)
    return `Datei darf maximal ${maxMB}MB groß sein`
  }
  return true
}

/**
 * Validate a value against multiple rules
 * Returns the first error message or true if all pass
 */
export function validate(value, rules) {
  for (const rule of rules) {
    const result = rule(value)
    if (result !== true) {
      return result
    }
  }
  return true
}
