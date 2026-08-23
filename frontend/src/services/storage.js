/**
 * Local storage service with TTL (time-to-live) support for caching.
 */

const CACHE_PREFIX = 'vocab_trainer_cache_'

/**
 * Save data to localStorage with optional TTL (in milliseconds)
 */
export function saveToCache(key, data, ttl = 0) {
  const cacheItem = {
    data,
    timestamp: Date.now(),
    ttl
  }
  try {
    localStorage.setItem(`${CACHE_PREFIX}${key}`, JSON.stringify(cacheItem))
  } catch (err) {
    // localStorage might be full, clear old entries
    console.warn('Cache storage failed:', err.message)
    clearExpiredCache()
  }
}

/**
 * Retrieve data from cache if not expired
 */
export function getFromCache(key) {
  try {
    const raw = localStorage.getItem(`${CACHE_PREFIX}${key}`)
    if (!raw) return null

    const cacheItem = JSON.parse(raw)

    // Check if TTL has expired
    if (cacheItem.ttl > 0) {
      const elapsed = Date.now() - cacheItem.timestamp
      if (elapsed > cacheItem.ttl) {
        localStorage.removeItem(`${CACHE_PREFIX}${key}`)
        return null
      }
    }

    return cacheItem.data
  } catch {
    return null
  }
}

/**
 * Remove a specific cache entry
 */
export function clearCache(key) {
  localStorage.removeItem(`${CACHE_PREFIX}${key}`)
}

/**
 * Clear all cache entries with our prefix
 */
export function clearAllCache() {
  const keysToRemove = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(CACHE_PREFIX)) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach((key) => localStorage.removeItem(key))
}

/**
 * Clear expired cache entries
 */
function clearExpiredCache() {
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(CACHE_PREFIX)) {
      try {
        const raw = localStorage.getItem(key)
        const cacheItem = JSON.parse(raw)
        if (cacheItem.ttl > 0) {
          const elapsed = Date.now() - cacheItem.timestamp
          if (elapsed > cacheItem.ttl) {
            localStorage.removeItem(key)
          }
        }
      } catch {
        localStorage.removeItem(key)
      }
    }
  }
}
