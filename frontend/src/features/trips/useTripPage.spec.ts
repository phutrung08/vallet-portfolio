import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { api } from '@/lib/api'
import { respond } from '@/features/trips/tripFixtures'
import { useTripPage } from '@/features/trips/useTripPage'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)
const fund = { holder_id: '1', contributed: 1000, spent: 400, remaining: 600 }

beforeEach(() => {
  get.mockReset()
})

describe('useTripPage', () => {
  it('skips /fund when trip has no holder and totals daily expenses', async () => {
    get.mockImplementation(respond())
    const page = useTripPage(() => 'abc')
    await flushPromises()
    expect(get.mock.calls.map(([path]) => path).sort()).toEqual([
      '/trips/abc',
      '/trips/abc/expenses/days',
    ])
    expect(page.fund.value).toBeNull()
    expect(page.spentTotal.value).toBe(500_000)
    expect(page.status.value).toBe('ready')
  })

  it('loads the fund summary with AbortSignal when the trip has a holder', async () => {
    get.mockImplementation(respond({ fund_holder_id: '1' }, fund))
    const page = useTripPage(() => 'abc')
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/trips/abc/fund', { signal: expect.any(AbortSignal) })
    expect(page.fund.value).toEqual(fund)
  })

  it('transitions to error state and recovers on reload', async () => {
    get.mockRejectedValue(new Error('boom'))
    const page = useTripPage(() => 'abc')
    await flushPromises()
    expect(page.status.value).toBe('error')
    get.mockImplementation(respond())
    await page.reload()
    expect(page.status.value).toBe('ready')
  })
})
