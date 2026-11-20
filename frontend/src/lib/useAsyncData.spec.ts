import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { api } from '@/lib/api'
import { useAsyncData } from '@/lib/useAsyncData'

function stubFetch(copies: Record<string, string | undefined>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const path = url.replace(/^\/api/, '')
      const headers: Record<string, string> = {}
      const date = copies[path]
      if (date !== undefined) Object.assign(headers, { 'X-Served-From': 'cache', Date: date })
      return Promise.resolve(new Response(JSON.stringify({ path }), { status: 200, headers }))
    }),
  )
}

const both = (signal: AbortSignal) =>
  Promise.all([api.get('/a', { signal }), api.get('/b', { signal })])

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useAsyncData offline copy', () => {
  it('is null when every answer came from the network', async () => {
    stubFetch({})
    const { cachedCopy, status } = useAsyncData(both)
    await flushPromises()
    expect(status.value).toBe('ready')
    expect(cachedCopy.value).toBeNull()
  })

  it('keeps the oldest saved time when the load used several copies', async () => {
    stubFetch({ '/a': 'Mon, 16 Nov 2026 09:00:00 GMT', '/b': 'Mon, 16 Nov 2026 07:05:00 GMT' })
    const { cachedCopy } = useAsyncData(both)
    await flushPromises()
    expect(cachedCopy.value).toEqual({ savedAt: new Date('2026-11-16T07:05:00Z') })
  })

  it('clears the notice after a refresh that reached the network', async () => {
    stubFetch({ '/a': 'Mon, 16 Nov 2026 09:00:00 GMT' })
    const { cachedCopy, refresh } = useAsyncData(both)
    await flushPromises()
    expect(cachedCopy.value).not.toBeNull()
    stubFetch({})
    await refresh()
    expect(cachedCopy.value).toBeNull()
  })
})

describe('useAsyncData concurrency and cleanup', () => {
  it('aborts earlier in-flight fetches and ignores stale responses on slower resolution', async () => {
    const signals: AbortSignal[] = []
    const resolvers: ((value: string) => void)[] = []

    const state = useAsyncData<string>(
      (signal) =>
        new Promise((resolve) => {
          signals.push(signal)
          resolvers.push(resolve)
        }),
    )

    expect(signals).toHaveLength(1)
    expect(signals[0]?.aborted).toBe(false)

    const second = state.refresh()
    expect(signals).toHaveLength(2)
    expect(signals[0]?.aborted).toBe(true)
    expect(signals[1]?.aborted).toBe(false)

    // Second finishes before first; later first resolution must never overwrite.
    resolvers[1]!('second')
    await second
    expect(state.data.value).toBe('second')
    expect(state.status.value).toBe('ready')

    resolvers[0]!('stale-first')
    await flushPromises()
    expect(state.data.value).toBe('second')
  })

  it('resets error state after recovery and ignores stale errors', async () => {
    let rejectFirst: (err: unknown) => void = () => {}
    let call = 0
    const state = useAsyncData<string>(
      () =>
        ++call === 1
          ? new Promise((_resolve, reject) => {
              rejectFirst = reject
            })
          : Promise.resolve('recovered'),
    )

    const refreshPromise = state.refresh()
    await refreshPromise
    expect(state.data.value).toBe('recovered')
    expect(state.status.value).toBe('ready')
    expect(state.error.value).toBeNull()

    rejectFirst(new Error('late stale failure'))
    await flushPromises()
    expect(state.status.value).toBe('ready')
    expect(state.error.value).toBeNull()
  })

  it('aborts active requests when its scope is disposed', async () => {
    let observedSignal: AbortSignal | undefined
    const scope = effectScope()
    scope.run(() =>
      useAsyncData(
        (signal) =>
          new Promise(() => {
            observedSignal = signal
          }),
      ),
    )

    expect(observedSignal?.aborted).toBe(false)
    scope.stop()
    expect(observedSignal?.aborted).toBe(true)
  })
})
