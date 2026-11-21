import { evictTripCacheOnAuthError, forgetAllTripCopies, invalidateAfterWrite } from '@/lib/offlineCache'

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface RequestOptions {
  body?: unknown
  idempotencyKey?: string
  signal?: AbortSignal
  timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 15000

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: unknown
  /** Field paths for a 422 validation_error, e.g. "body.member_names". */
  readonly fields: readonly string[]
  /** Total minus stated amounts for an exact split mismatch (invalid_split). */
  readonly difference?: number

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    fields: readonly string[] = [],
    difference?: number,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.fields = fields
    this.difference = difference
  }
}

function baseUrl(): string {
  const configured: unknown = import.meta.env.VITE_API_BASE_URL
  const base = typeof configured === 'string' && configured !== '' ? configured : '/api'
  return base.replace(/\/+$/, '')
}

function buildUrl(path: string): string {
  // Cookies ride every request, so reject protocol-relative or cross-origin paths.
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new TypeError('API path must start with a single "/"')
  }
  return baseUrl() + path
}

function buildHeaders(options: RequestOptions): Headers {
  const headers = new Headers({ Accept: 'application/json', 'X-Requested-With': 'vallet' })
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')
  if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey)
  return headers
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

async function readJson(response: Response): Promise<{ ok: boolean; value: unknown }> {
  const text = await response.text().catch(() => '')
  if (text === '') return { ok: true, value: undefined }
  try {
    return { ok: true, value: JSON.parse(text) }
  } catch {
    return { ok: false, value: undefined }
  }
}

function httpError(status: number, parsed: { ok: boolean; value: unknown }): ApiError {
  const body = parsed.ok && isRecord(parsed.value) ? parsed.value : undefined
  const code = typeof body?.code === 'string' ? body.code : 'http_error'
  const message = typeof body?.message === 'string' ? body.message : 'Request failed'
  const fields = Array.isArray(body?.fields)
    ? body.fields.filter((field): field is string => typeof field === 'string')
    : []
  const difference = typeof body?.difference === 'number' ? body.difference : undefined
  return new ApiError(status, code, message, body?.details, fields, difference)
}

async function send(url: string, method: Method, options: RequestOptions): Promise<Response> {
  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  const signal = options.signal ? AbortSignal.any([options.signal, timeout.signal]) : timeout.signal
  try {
    return await fetch(url, {
      method,
      headers: buildHeaders(options),
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: 'include',
      signal,
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    if (timeout.signal.aborted) throw new ApiError(0, 'timeout', 'Request timed out')
    throw new ApiError(0, 'network_error', 'Network error')
  } finally {
    clearTimeout(timer)
  }
}

/** Offline cache metadata reported when the service worker satisfies a read request. */
export interface CachedCopy {
  savedAt: Date | null
}

const cachedCopyListeners = new Set<(copy: CachedCopy) => void>()

/** Subscribe to notifications emitted when a response is served from the SW offline cache. */
export function onCachedCopy(listener: (copy: CachedCopy) => void): () => void {
  cachedCopyListeners.add(listener)
  return () => cachedCopyListeners.delete(listener)
}

function reportCachedCopy(response: Response): void {
  if (response.headers.get('X-Served-From') !== 'cache') return
  const savedAt = new Date(response.headers.get('Date') ?? '')
  const copy = { savedAt: Number.isNaN(savedAt.getTime()) ? null : savedAt }
  for (const listener of cachedCopyListeners) listener(copy)
}

function evictCacheOnAuthError(path: string, status: number): void {
  if (status === 401) {
    void forgetAllTripCopies().catch(() => undefined)
    return
  }
  if (status !== 403 && status !== 404) return
  const match = /^\/trips\/([^/?#]+)(?:[/?#]|$)/.exec(path)
  if (!match?.[1]) return
  let tripId = match[1]
  try {
    tripId = decodeURIComponent(tripId)
  } catch {
    // Keep the raw path segment if percent decoding fails.
  }
  void evictTripCacheOnAuthError(tripId, status).catch(() => undefined)
}

export async function apiRequest<T>(
  method: Method,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  if (method !== 'GET' && !navigator.onLine) throw new ApiError(0, 'offline', 'Offline')
  const response = await send(buildUrl(path), method, options)
  reportCachedCopy(response)
  const parsed = await readJson(response)
  if (!response.ok) {
    evictCacheOnAuthError(path, response.status)
    throw httpError(response.status, parsed)
  }
  if (!parsed.ok) throw new ApiError(response.status, 'invalid_response', 'Invalid server response')
  if (method !== 'GET') await invalidateAfterWrite(path).catch(() => undefined)
  return parsed.value as T
}

type BodylessOptions = Omit<RequestOptions, 'body'>

export const api = {
  get: <T>(path: string, options?: BodylessOptions) => apiRequest<T>('GET', path, options),
  post: <T>(path: string, body?: unknown, options?: BodylessOptions) =>
    apiRequest<T>('POST', path, { ...options, body }),
  put: <T>(path: string, body?: unknown, options?: BodylessOptions) =>
    apiRequest<T>('PUT', path, { ...options, body }),
  patch: <T>(path: string, body?: unknown, options?: BodylessOptions) =>
    apiRequest<T>('PATCH', path, { ...options, body }),
  delete: <T>(path: string, options?: BodylessOptions) => apiRequest<T>('DELETE', path, options),
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}
