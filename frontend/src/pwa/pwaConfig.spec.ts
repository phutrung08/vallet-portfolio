import { describe, expect, it } from 'vitest'
import {
  API_CACHE_NAME,
  isOfflineReadable,
  markServedFromCache,
  pwaOptions,
  storableResponse,
} from '@/pwa/pwaConfig'

const ORIGIN = 'https://app.example'

function match(path: string, method = 'GET', sameOrigin = true): boolean {
  const url = new URL(path, ORIGIN)
  return isOfflineReadable({ url, request: new Request(url, { method }), sameOrigin })
}

// Workbox copies these functions into sw.js as source text, so each must run standalone.
function rebuilt<F>(fn: F): F {
  return (0, eval)(`(${String(fn)})`) as F
}

const runtime = pwaOptions.workbox?.runtimeCaching ?? []

describe('isOfflineReadable', () => {
  it.each([
    '/api/trips',
    '/api/trips/abc',
    '/api/trips/abc/expenses/days',
    '/api/trips/abc/expenses?day=2026-11-06',
    '/api/trips/abc/balances',
    '/api/trips/abc/payments',
    '/api/trips/abc/fund',
    '/api/trips/abc/summary',
  ])('keeps a copy of GET %s', (path) => {
    expect(match(path)).toBe(true)
  })

  it.each([
    ['the share link (no-store)', '/api/trips/abc/share-link'],
    ['a VietQR payload (no-store)', '/api/trips/abc/vietqr?payee=x&amount=1'],
    ['the join preview (no-store)', '/api/join/preview'],
    ['joining', '/api/join'],
    ['anything outside trips', '/api/banks'],
    ['an app page', '/trips/abc'],
    ['a look-alike prefix', '/api/tripsx'],
  ])('never caches %s', (_name, path) => {
    expect(match(path)).toBe(false)
  })

  it('never caches writes or other origins', () => {
    for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
      expect(match('/api/trips/abc', method)).toBe(false)
    }
    expect(match('/api/trips/abc', 'GET', false)).toBe(false)
  })

  it('still works as standalone source text written into the service worker', () => {
    const copy = rebuilt(isOfflineReadable)
    const blocked = new URL('/api/trips/abc/share-link', ORIGIN)
    expect(copy({ url: blocked, request: new Request(blocked), sameOrigin: true })).toBe(false)
    const allowed = new URL('/api/trips/abc', ORIGIN)
    expect(copy({ url: allowed, request: new Request(allowed), sameOrigin: true })).toBe(true)
  })
})

describe('storableResponse', () => {
  const answer = (status: number, cacheControl?: string) =>
    new Response('{}', { status, headers: cacheControl ? { 'Cache-Control': cacheControl } : {} })

  it.each([
    ['no-store', 'no-store'],
    ['no-store among others', 'private, no-store, max-age=0'],
    ['upper case', 'NO-STORE'],
  ])('refuses a response marked %s', async (_name, header) => {
    expect(await storableResponse({ response: answer(200, header) })).toBeNull()
  })

  it.each([204, 304, 404, 500])('refuses status %i', async (status) => {
    const response = new Response(status === 204 || status === 304 ? null : '{}', { status })
    expect(await storableResponse({ response })).toBeNull()
  })

  it('keeps a plain 200 and one with other cache directives', async () => {
    const plain = answer(200)
    expect(await storableResponse({ response: plain })).toBe(plain)
    const privateOne = answer(200, 'private, max-age=60')
    expect(await rebuilt(storableResponse)({ response: privateOne })).toBe(privateOne)
    const privateNoCache = answer(200, 'private, no-cache')
    expect(await rebuilt(storableResponse)({ response: privateNoCache })).toBe(privateNoCache)
    expect(await rebuilt(storableResponse)({ response: answer(200, 'no-store') })).toBeNull()
  })
})

describe('markServedFromCache', () => {
  it('adds X-Served-From and keeps status, Date and body', async () => {
    const cached = new Response('{"a":1}', {
      status: 200,
      headers: { Date: 'Mon, 16 Nov 2026 07:05:00 GMT', 'Content-Type': 'application/json' },
    })
    const marked = await rebuilt(markServedFromCache)({ cachedResponse: cached })
    expect(marked?.headers.get('X-Served-From')).toBe('cache')
    expect(marked?.headers.get('Date')).toBe('Mon, 16 Nov 2026 07:05:00 GMT')
    expect(marked?.status).toBe(200)
    expect(await marked?.text()).toBe('{"a":1}')
  })

  it('passes a cache miss through', async () => {
    expect(await markServedFromCache({ cachedResponse: undefined })).toBeUndefined()
  })
})

describe('pwaOptions', () => {
  it('uses the prompt flow and keeps the hand-written manifest', () => {
    expect(pwaOptions.registerType).toBe('prompt')
    expect(pwaOptions.manifest).toBe(false)
  })

  it('falls back to index.html for app routes but never for /api', () => {
    const deny = pwaOptions.workbox?.navigateFallbackDenylist ?? []
    expect(pwaOptions.workbox?.navigateFallback).toBe('index.html')
    expect(deny.some((pattern) => pattern.test('/api/trips/abc'))).toBe(true)
    expect(deny.some((pattern) => pattern.test('/trips/abc/balances'))).toBe(false)
  })

  it('has one API route: GET, network first, bounded, with the no-store guard', () => {
    expect(runtime).toHaveLength(1)
    const [route] = runtime
    expect(route?.method).toBe('GET')
    expect(route?.handler).toBe('NetworkFirst')
    expect(route?.urlPattern).toBe(isOfflineReadable)
    expect(route?.options).toMatchObject({
      cacheName: API_CACHE_NAME,
      networkTimeoutSeconds: 10,
      cacheableResponse: { statuses: [200] },
      expiration: { maxEntries: 300, maxAgeSeconds: 30 * 24 * 60 * 60 },
    })
    expect(route?.options?.plugins).toEqual([
      { cacheWillUpdate: storableResponse, cachedResponseWillBeUsed: markServedFromCache },
    ])
  })
})
