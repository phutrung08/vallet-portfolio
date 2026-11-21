/** Name of the service worker runtime cache holding API trip responses. */
export const API_CACHE_NAME = 'vallet-api-v1'

const AUTH_OR_MISSING_STATUSES = new Set([401, 403, 404])

/** Deletes the entire offline copy of API responses (for example, on device sign-out). */
export async function forgetAllTripCopies(): Promise<void> {
  if (typeof caches === 'undefined') return
  await caches.delete(API_CACHE_NAME)
}

async function deleteCachedPaths(matches: (pathname: string) => boolean): Promise<void> {
  if (typeof caches === 'undefined') return
  const cache = await caches.open(API_CACHE_NAME)
  const keys = await cache.keys()
  const targets = keys.filter((request) => matches(new URL(request.url).pathname))
  await Promise.all(targets.map((request) => cache.delete(request)))
}

function tripIdFromApiPath(path: string): string | null {
  const segment = /^\/trips\/([^/?#]+)/.exec(path)?.[1]
  if (!segment) return null
  try {
    return decodeURIComponent(segment)
  } catch {
    return segment
  }
}

/** Deletes this device's offline copy of the cached trip list. */
export async function forgetTripListCopy(): Promise<void> {
  await deleteCachedPaths((path) => path === '/api/trips')
}

/**
 * Deletes this device's offline copy of one trip so a trip the user left or lost access to
 * cannot remain readable from cached API responses.
 */
export async function forgetTripCopy(tripId: string): Promise<void> {
  const prefix = `/api/trips/${encodeURIComponent(tripId)}`
  await deleteCachedPaths((path) => path === prefix || path.startsWith(`${prefix}/`))
}

/** Evicts cached trip API responses whenever the backend returns 401, 403, or 404. */
export async function evictTripCacheOnAuthError(tripId: string, status: number): Promise<void> {
  if (!AUTH_OR_MISSING_STATUSES.has(status)) return
  await forgetTripCopy(tripId)
}

/**
 * Invalidates cached trip API responses after a successful mutation so the next load
 * reflects fresh server state instead of stale Workbox cache.
 */
export async function invalidateAfterWrite(path: string): Promise<void> {
  const cleanPath = path.split(/[?#]/, 1)[0] ?? ''
  const tripId = tripIdFromApiPath(cleanPath)
  if (tripId) {
    await Promise.all([forgetTripCopy(tripId), forgetTripListCopy()])
    return
  }
  if (cleanPath === '/trips' || cleanPath === '/join') {
    await forgetTripListCopy()
  }
}
