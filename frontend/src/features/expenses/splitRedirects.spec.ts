import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RouteLocationNormalized } from 'vue-router'
import { expense } from '@/features/expenses/expenseFixtures'
import { addToPane, openInPane } from '@/features/expenses/splitRedirects'
import { ApiError, api } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)
const sampleBill = expense({ a: 50_000, b: 50_000 })

function to(name: string): RouteLocationNormalized {
  return { name, params: { tripId: 'abc', expenseId: 'e1' } } as unknown as RouteLocationNormalized
}

function run(guard: typeof openInPane, route: RouteLocationNormalized) {
  return guard(route, route, () => undefined)
}

function mockWide(wide: boolean) {
  vi.stubGlobal('matchMedia', () => ({ matches: wide }))
}

beforeEach(() => {
  get.mockReset()
  get.mockResolvedValue(sampleBill)
})

describe('full-screen expense route redirects', () => {
  it('preserves full-screen routes below the split breakpoint', async () => {
    mockWide(false)
    expect(await run(addToPane, to('new-expense'))).toBe(true)
    expect(await run(openInPane, to('expense'))).toBe(true)
    expect(get).not.toHaveBeenCalled()
  })

  it('redirects new-expense to the split Add pane', async () => {
    mockWide(true)
    expect(await run(addToPane, to('new-expense'))).toEqual({
      path: '/trips/abc',
      query: { pane: 'add' },
      replace: true,
    })
  })

  it('opens detail and edit links inside the split pane on the matching day', async () => {
    mockWide(true)
    const query = { day: sampleBill.spent_on, expense: sampleBill.id }
    expect(await run(openInPane, to('expense'))).toEqual({ path: '/trips/abc', query, replace: true })
    expect(await run(openInPane, to('edit-expense'))).toEqual({
      path: '/trips/abc',
      query: { ...query, edit: 'yes' },
      replace: true,
    })
  })

  it('leaves standalone page active when expense lookup fails', async () => {
    mockWide(true)
    get.mockRejectedValue(new ApiError(404, 'not_found', 'gone'))
    expect(await run(openInPane, to('expense'))).toBe(true)
  })
})
