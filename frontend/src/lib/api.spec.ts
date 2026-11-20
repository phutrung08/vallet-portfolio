import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, apiRequest, newIdempotencyKey, onCachedCopy } from '@/lib/api'

type FetchMock = ReturnType<typeof vi.fn>

function respond(body: string | null, status = 200): FetchMock {
  const mock = vi.fn(() => Promise.resolve(new Response(body, { status })))
  vi.stubGlobal('fetch', mock)
  return mock
}

function hangUntilAborted(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(new DOMException('', 'AbortError')))
        }),
    ),
  )
}

function lastCall(mock: FetchMock): [string, RequestInit] {
  return mock.mock.calls[0] as [string, RequestInit]
}

function rejection(promise: Promise<unknown>): Promise<unknown> {
  return promise.then(
    () => undefined,
    (error: unknown) => error,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.useRealTimers()
})

describe('request shape', () => {
  it.each([
    ['unset base', '', '/api/trips'],
    ['base without slash', 'http://localhost:8000', 'http://localhost:8000/trips'],
    ['base with trailing slash', 'http://localhost:8000/', 'http://localhost:8000/trips'],
  ])('joins the URL: %s', async (_name, base, expected) => {
    vi.stubEnv('VITE_API_BASE_URL', base)
    const mock = respond('{}')
    await apiRequest('GET', '/trips')
    expect(lastCall(mock)[0]).toBe(expected)
  })

  it('sends cookies and the fixed headers without a body', async () => {
    const mock = respond('{}')
    await apiRequest('DELETE', '/trips/1')
    const init = lastCall(mock)[1]
    const headers = new Headers(init.headers)
    expect(init.method).toBe('DELETE')
    expect(init.credentials).toBe('include')
    expect(init.body).toBeUndefined()
    expect(headers.get('Accept')).toBe('application/json')
    expect(headers.get('X-Requested-With')).toBe('vallet')
    expect(headers.has('Content-Type')).toBe(false)
    expect(headers.has('Idempotency-Key')).toBe(false)
  })

  it('sends a JSON body and the idempotency key when given', async () => {
    const mock = respond('{}')
    await api.post('/expenses', { amount: 5 }, { idempotencyKey: 'key-1' })
    const init = lastCall(mock)[1]
    const headers = new Headers(init.headers)
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"amount":5}')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Idempotency-Key')).toBe('key-1')
  })

  it.each(['put', 'patch'] as const)('api.%s uses its method', async (name) => {
    const mock = respond('{}')
    await api[name]('/x', {})
    expect(lastCall(mock)[1].method).toBe(name.toUpperCase())
  })
})

describe('responses', () => {
  it('parses a JSON body', async () => {
    respond('{"id":"a"}')
    expect(await api.get('/trips/a')).toEqual({ id: 'a' })
  })

  it.each([
    ['204', null, 204],
    ['empty 200', '', 200],
  ])('resolves undefined for %s', async (_name, body, status) => {
    respond(body, status)
    expect(await api.get('/x')).toBeUndefined()
  })

  it('maps an error body to ApiError', async () => {
    respond('{"code":"trip_locked","message":"Locked","details":{"a":1}}', 409)
    const error = await rejection(api.get('/x'))
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 409,
      code: 'trip_locked',
      message: 'Locked',
      details: { a: 1 },
    })
  })

  it('keeps the field paths of a validation error', async () => {
    respond('{"code":"validation_error","message":"Invalid","fields":["body.name"]}', 422)
    expect(await rejection(api.get('/x'))).toMatchObject({ fields: ['body.name'] })
  })

  it('keeps the difference of an invalid split', async () => {
    respond('{"code":"invalid_split","message":"Split","difference":-2000}', 422)
    expect(await rejection(api.get('/x'))).toMatchObject({ difference: -2000 })
    respond('{"code":"invalid_split","message":"Split","difference":"x"}', 422)
    expect(await rejection(api.get('/x'))).toMatchObject({ difference: undefined })
  })

  it.each([
    ['non-JSON', '<html>secret</html>'],
    ['JSON without code', '{"detail":"x"}'],
  ])('falls back to http_error for %s', async (_name, body) => {
    respond(body, 500)
    const error = await rejection(api.get('/x'))
    expect(error).toMatchObject({ status: 500, code: 'http_error', message: 'Request failed' })
  })

  it('rejects a malformed success body as invalid_response', async () => {
    respond('{oops', 200)
    expect(await rejection(api.get('/x'))).toMatchObject({ code: 'invalid_response' })
  })
})

describe('failures', () => {
  it('maps a fetch failure to network_error', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    expect(await rejection(api.get('/x'))).toMatchObject({ status: 0, code: 'network_error' })
  })

  it('rejects with timeout when the deadline passes', async () => {
    vi.useFakeTimers()
    hangUntilAborted()
    const pending = rejection(api.get('/x', { timeoutMs: 1000 }))
    await vi.advanceTimersByTimeAsync(1000)
    expect(await pending).toMatchObject({ status: 0, code: 'timeout' })
  })

  it('propagates a caller abort unwrapped', async () => {
    hangUntilAborted()
    const controller = new AbortController()
    const pending = rejection(api.get('/x', { signal: controller.signal }))
    controller.abort()
    const error = await pending
    expect(error).not.toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ name: 'AbortError' })
  })
})

describe('path safety', () => {
  it.each(['https://evil.example/x', '//evil.example/x', 'trips', ''])(
    'throws TypeError for %j and never calls fetch',
    async (path) => {
      const mock = respond('{}')
      expect(await rejection(apiRequest('GET', path))).toBeInstanceOf(TypeError)
      expect(mock).not.toHaveBeenCalled()
    },
  )
})

describe('newIdempotencyKey', () => {
  it('returns distinct UUID-shaped strings', () => {
    const [a, b] = [newIdempotencyKey(), newIdempotencyKey()]
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/)
    expect(a).not.toBe(b)
  })
})

describe('offline writes', () => {
  afterEach(() => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
  })

  it.each(['POST', 'PUT', 'PATCH', 'DELETE'] as const)(
    'rejects %s with offline at once, without calling fetch',
    async (method) => {
      Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
      const mock = respond('{}')
      const error = await rejection(apiRequest(method, '/trips/1', { body: {} }))
      expect(error).toBeInstanceOf(ApiError)
      expect(error).toMatchObject({ status: 0, code: 'offline' })
      expect(mock).not.toHaveBeenCalled()
    },
  )

  it('still sends a GET, which the offline copy may answer', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    const mock = respond('{"ok":true}')
    expect(await api.get('/trips/1')).toEqual({ ok: true })
    expect(mock).toHaveBeenCalledTimes(1)
  })
})

describe('offline copy signal', () => {
  function respondWith(headers: Record<string, string>): void {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('{}', { status: 200, headers }))))
  }

  it('reports an answer the service worker marked, with its Date as savedAt', async () => {
    const listener = vi.fn()
    const stop = onCachedCopy(listener)
    respondWith({ 'X-Served-From': 'cache', Date: 'Mon, 16 Nov 2026 07:05:00 GMT' })
    await api.get('/trips/1')
    stop()
    expect(listener).toHaveBeenCalledWith({ savedAt: new Date('2026-11-16T07:05:00Z') })
  })

  it('reports savedAt null when the copy has no usable Date', async () => {
    const listener = vi.fn()
    const stop = onCachedCopy(listener)
    respondWith({ 'X-Served-From': 'cache', Date: 'nonsense' })
    await api.get('/trips/1')
    stop()
    expect(listener).toHaveBeenCalledWith({ savedAt: null })
  })

  it('stays quiet for a network answer and after unsubscribing', async () => {
    const listener = vi.fn()
    const stop = onCachedCopy(listener)
    respondWith({ Date: 'Mon, 16 Nov 2026 07:05:00 GMT' })
    await api.get('/trips/1')
    stop()
    respondWith({ 'X-Served-From': 'cache' })
    await api.get('/trips/1')
    expect(listener).not.toHaveBeenCalled()
  })
})
