import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { useDayExpenses } from '@/features/expenses/useDayExpenses'
import { ApiError, api } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)
const listing = (title: string) => ({ expenses: [{ id: title, title }] })

beforeEach(() => {
  get.mockReset()
})

describe('useDayExpenses', () => {
  it('loads each visited day once with AbortSignal and serves cached days immediately', async () => {
    get.mockImplementation((path) =>
      Promise.resolve(listing(path.endsWith('2026-11-06') ? 'six' : 'five')),
    )
    const day = ref('2026-11-06')
    const result = useDayExpenses(
      () => 'abc',
      () => day.value,
    )
    expect(result.status.value).toBe('loading')
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/trips/abc/expenses?day=2026-11-06', {
      signal: expect.any(AbortSignal),
    })
    expect(result.expenses.value.map((e) => e.title)).toEqual(['six'])

    day.value = '2026-11-05'
    await flushPromises()
    expect(result.expenses.value.map((e) => e.title)).toEqual(['five'])

    day.value = '2026-11-06'
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(result.status.value).toBe('ready')
    expect(result.expenses.value.map((e) => e.title)).toEqual(['six'])
  })

  it('enters error state and recovers on reload for the active day', async () => {
    get.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    const result = useDayExpenses(
      () => 'abc',
      () => '2026-11-06',
    )
    await flushPromises()
    expect(result.status.value).toBe('error')
    get.mockResolvedValueOnce(listing('six'))
    await result.reload()
    expect(result.status.value).toBe('ready')
    expect(result.expenses.value).toHaveLength(1)
  })

  it('re-fetches an invalidated day immediately only if currently displayed', async () => {
    get.mockImplementation((path) => Promise.resolve(listing(path.slice(-2))))
    const day = ref('2026-11-06')
    const result = useDayExpenses(
      () => 'abc',
      () => day.value,
    )
    await flushPromises()
    day.value = '2026-11-05'
    await flushPromises()
    await result.invalidate('2026-11-06')
    expect(get).toHaveBeenCalledTimes(2)
    await result.invalidate('2026-11-05')
    expect(get).toHaveBeenCalledTimes(3)
    day.value = '2026-11-06'
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(4)
  })

  it('aborts and ignores stale errors from a day the user navigated away from', async () => {
    let fail: (reason: unknown) => void = () => undefined
    get.mockImplementationOnce(() => new Promise((_, reject) => (fail = reject)))
    get.mockResolvedValueOnce(listing('five'))
    const day = ref('2026-11-06')
    const result = useDayExpenses(
      () => 'abc',
      () => day.value,
    )
    day.value = '2026-11-05'
    await flushPromises()
    fail(new ApiError(0, 'network_error', 'Network error'))
    await flushPromises()
    expect(result.status.value).toBe('ready')
    expect(result.expenses.value.map((e) => e.title)).toEqual(['five'])
  })

  it('refreshes active day in place and drops inactive day cache entries', async () => {
    let call = 0
    get.mockImplementation(() => Promise.resolve(listing(`v${++call}`)))
    const day = ref('2026-11-06')
    const result = useDayExpenses(
      () => 'abc',
      () => day.value,
    )
    await flushPromises()
    day.value = '2026-11-05'
    await flushPromises()
    expect(result.expenses.value.map((e) => e.title)).toEqual(['v2'])

    const pending = result.refreshAll()
    expect(result.status.value).toBe('ready')
    expect(result.expenses.value.map((e) => e.title)).toEqual(['v2'])
    await pending
    expect(result.expenses.value.map((e) => e.title)).toEqual(['v3'])

    day.value = '2026-11-06'
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(4)
    expect(result.expenses.value.map((e) => e.title)).toEqual(['v4'])
  })
})
