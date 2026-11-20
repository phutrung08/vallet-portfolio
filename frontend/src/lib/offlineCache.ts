/** Name of the service worker runtime cache holding API trip responses. */
export const API_CACHE_NAME = 'vallet-api-v1'

const AUTH_OR_MISSING_STATUSES = new Set([401, 403, 404])

/** Deletes the entire offline copy of API responses (for example, on device sign-out). */
export async function forgetAllTripCopies(): Promise<void> {
  if (typeof caches === 'undefined') return
  await caches.delete(API_CACHE_NAME)
}

/**
 * Deletes this device's offline copy of one trip so a trip the user left or lost access to
 * cannot remain readable from cached API responses.
 */
export async function forgetTripCopy(tripId: string): Promise<void> {
  if (typeof caches === 'undefined') return
  const cache = await caches.open(API_CACHE_NAME)
  const prefix = `/api/trips/${encodeURIComponent(tripId)}`
  const keys = await cache.keys()
  const own = keys.filter((request) => {
    const path = new URL(request.url).pathname
    return path === prefix || path.startsWith(`${prefix}/`)
  })
  await Promise.all(own.map((request) => cache.delete(request)))
}

/** Evicts cached trip API responses whenever the backend returns 401, 403, or 404. */
export async function evictTripCacheOnAuthError(tripId: string, status: number): Promise<void> {
  if (!AUTH_OR_MISSING_STATUSES.has(status)) return
  await forgetTripCopy(tripId)
}
