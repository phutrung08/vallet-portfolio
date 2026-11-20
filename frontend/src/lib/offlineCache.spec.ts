import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  API_CACHE_NAME,
  evictTripCacheOnAuthError,
  forgetAllTripCopies,
  forgetTripCopy,
} from '@/lib/offlineCache'

const ORIGIN = 'https://app.example'

function stubCaches(urls: string[]) {
  const stored = urls.map((url) => new Request(`${ORIGIN}${url}`))
  const cache = {
    keys: vi.fn(() => Promise.resolve(stored)),
    delete: vi.fn((request: Request) => Promise.resolve(stored.includes(request))),
  }
  const open = vi.fn(() => Promise.resolve(cache))
  const delCache = vi.fn(() => Promise.resolve(true))
  vi.stubGlobal('caches', { open, delete: delCache })
  const deleted = () =>
    cache.delete.mock.calls.map(([request]) => {
      const url = new URL(request.url)
      return url.pathname + url.search
    })
  return { open, delCache, deleted }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('forgetTripCopy', () => {
  it("deletes only that trip's API entries without touching sibling trips", async () => {
    const { open, deleted } = stubCaches([
      '/api/trips',
      '/api/trips/abc',
      '/api/trips/abc/balances',
      '/api/trips/abc/expenses?day=2026-11-06',
      '/api/trips/abcd',
      '/api/trips/abcd/fund',
      '/api/trips/other/balances',
    ])
    await forgetTripCopy('abc')
    expect(open).toHaveBeenCalledWith(API_CACHE_NAME)
    expect(deleted()).toEqual([
      '/api/trips/abc',
      '/api/trips/abc/balances',
      '/api/trips/abc/expenses?day=2026-11-06',
    ])
  })

  it('encodes special trip IDs cleanly before matching URL pathnames', async () => {
    const { deleted } = stubCaches([
      '/api/trips/trip%201',
      '/api/trips/trip%201/fund',
      '/api/trips/trip%2010',
    ])
    await forgetTripCopy('trip 1')
    expect(deleted()).toEqual(['/api/trips/trip%201', '/api/trips/trip%201/fund'])
  })

  it('is a no-op when the Cache API is unavailable', async () => {
    vi.stubGlobal('caches', undefined)
    await expect(forgetTripCopy('abc')).resolves.toBeUndefined()
    await expect(forgetAllTripCopies()).resolves.toBeUndefined()
  })
})

describe('forgetAllTripCopies', () => {
  it('deletes the entire API cache bucket', async () => {
    const { delCache } = stubCaches([])
    await forgetAllTripCopies()
    expect(delCache).toHaveBeenCalledWith(API_CACHE_NAME)
  })
})

describe('evictTripCacheOnAuthError', () => {
  it.each([401, 403, 404])('evicts trip cache on status %i', async (status) => {
    const { deleted } = stubCaches(['/api/trips/abc', '/api/trips/abc/balances'])
    await evictTripCacheOnAuthError('abc', status)
    expect(deleted()).toEqual(['/api/trips/abc', '/api/trips/abc/balances'])
  })

  it.each([500, 503])('leaves trip cache intact on status %i', async (status) => {
    const { open, deleted } = stubCaches(['/api/trips/abc'])
    await evictTripCacheOnAuthError('abc', status)
    expect(open).not.toHaveBeenCalled()
    expect(deleted()).toEqual([])
  })
})
