import type { VitePWAOptions } from 'vite-plugin-pwa'

/** Service worker runtime cache holding offline-readable trip API GET responses. */
export const API_CACHE_NAME = 'vallet-api-v1'

/*
 * Workbox serializes the callbacks below directly into the generated sw.js via Function#toString(),
 * so every helper below must stay strictly self-contained without module imports or outer closures.
 */

interface RouteMatch {
  url: URL
  request: Request
  sameOrigin: boolean
}

/** Matches read-only trip GET requests safe to cache offline; excludes share links, VietQR, and join flows. */
export function isOfflineReadable({ url, request, sameOrigin }: RouteMatch): boolean {
  return (
    request.method === 'GET' &&
    sameOrigin &&
    /^\/api\/trips(\/|$)/.test(url.pathname) &&
    !/^\/api\/join|\/share-link(\/|$)|\/vietqr(\/|$)/.test(url.pathname)
  )
}

/** Prevents caching responses marked `Cache-Control: no-store` or non-200 status codes. */
export async function storableResponse({
  response,
}: {
  response: Response
}): Promise<Response | null> {
  const cacheControl = response.headers.get('Cache-Control') ?? ''
  return response.status === 200 && !/(^|[\s,])no-store([\s,;]|$)/i.test(cacheControl)
    ? response
    : null
}

/** Flags responses served from Cache Storage so the UI can show an offline-copy notice with its timestamp. */
export async function markServedFromCache({
  cachedResponse,
}: {
  cachedResponse?: Response
}): Promise<Response | undefined> {
  if (!cachedResponse) return cachedResponse
  const headers = new Headers(cachedResponse.headers)
  headers.set('X-Served-From', 'cache')
  return new Response(cachedResponse.body, {
    status: cachedResponse.status,
    statusText: cachedResponse.statusText,
    headers,
  })
}

export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: 'prompt',
  // Registered explicitly in App.vue via useRegisterSW so the update toast prompts before reloading.
  injectRegister: false,
  // public/manifest.webmanifest and its link in index.html remain the manifest source of truth.
  manifest: false,
  workbox: {
    globPatterns: ['**/*.{js,css,html,woff2,svg,png,webmanifest}'],
    navigateFallback: 'index.html',
    navigateFallbackDenylist: [/^\/api(\/|$)/],
    cleanupOutdatedCaches: true,
    runtimeCaching: [
      {
        urlPattern: isOfflineReadable,
        method: 'GET',
        handler: 'NetworkFirst',
        options: {
          cacheName: API_CACHE_NAME,
          networkTimeoutSeconds: 10,
          cacheableResponse: { statuses: [200] },
          expiration: { maxEntries: 300, maxAgeSeconds: 30 * 24 * 60 * 60, purgeOnQuotaError: true },
          plugins: [
            { cacheWillUpdate: storableResponse, cachedResponseWillBeUsed: markServedFromCache },
          ],
        },
      },
    ],
  },
}
