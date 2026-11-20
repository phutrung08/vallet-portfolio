import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Expense, TripDetail } from '@/entities'
import ExpenseDetailView from '@/features/expenses/ExpenseDetailView.vue'
import { expense } from '@/features/expenses/expenseFixtures'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { dialog } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const del = vi.mocked(api.delete)
const stub = { template: '<div />' }
let wrapper: VueWrapper | undefined

const percentSplit = expense(
  { '1': 60_000, '3': 40_000 },
  {
    title: 'Hotpot',
    split_mode: 'percent',
    shares: [
      { member_id: '1', weight: 6_000, amount: 60_000 },
      { member_id: '3', weight: 4_000, amount: 40_000 },
    ],
    paid_by: '2',
    note: 'Corner stall',
    place: 'Da Lat Market',
    created_by: '1',
    updated_by: '2',
    spent_on: '2026-11-06',
  },
)

async function mountDetail(stored: Expense = percentSplit, tripOverrides: Partial<TripDetail> = {}) {
  get.mockImplementation((path: string) =>
    Promise.resolve(path === '/trips/abc' ? { ...trip, ...tripOverrides } : stored),
  )
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/trips/:tripId', component: stub },
      { path: '/trips/:tripId/expenses/:expenseId', component: ExpenseDetailView },
      { path: '/trips/:tripId/expenses/:expenseId/edit', component: stub },
    ],
  })
  await router.push('/trips/abc/expenses/e1')
  wrapper = mount(ExpenseDetailView, {
    attachTo: document.body,
    global: { plugins: [createAppI18n('en'), router] },
  })
  await flushPromises()
  return { wrapper, router }
}

const text = (node: { text: () => string }) => node.text().replaceAll('\u00a0', ' ')
const sheetButton = (label: string) =>
  [...(dialog()?.querySelectorAll('button') ?? [])].find((b) => b.textContent?.trim() === label)

beforeEach(() => {
  get.mockReset()
  del.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('ExpenseDetailView', () => {
  it('displays amount, metadata, share weights, note, place, and authorship', async () => {
    const { wrapper } = await mountDetail()
    expect(get).toHaveBeenCalledWith('/trips/abc/expenses/e1', { signal: expect.any(AbortSignal) })
    expect(wrapper.get('h1').text()).toBe('Hotpot')
    const all = text(wrapper)
    expect(all).toContain('₫100,000')
    expect(all).toContain('Food · 11/6')
    expect(all).toContain('Paid by: Ben · split by percent')
    expect(wrapper.findAll('li').map((row) => text(row))).toEqual([
      'AAlex60%₫60,000',
      'FFormer guest (left)40%₫40,000',
    ])
    expect(all).toContain('Corner stall')
    expect(wrapper.get('a[target="_blank"]').text()).toBe('Da Lat Market')
    expect(all).toContain('Added by Alex · Last edited by Ben')
    expect(wrapper.get('a[href="/trips/abc/expenses/e1/edit"]').text()).toBe('Edit expense')
  })

  it('displays share counts and Group fund label', async () => {
    const shares = expense({ '1': 200, '2': 100 }, { split_mode: 'shares', paid_by: null })
    shares.shares = shares.shares.map((share) => ({ ...share, weight: share.amount / 100 }))
    const { wrapper } = await mountDetail(shares)
    expect(text(wrapper)).toContain('Paid by: Group fund')
    expect(wrapper.findAll('li').map((row) => text(row))).toEqual(['AAlex2 shares₫200', 'BBen1 share₫100'])
  })

  it('confirms deletion in native dialog before deleting and navigating back to day view', async () => {
    const { wrapper, router } = await mountDetail()
    const deleteButton = wrapper.findAll('button').find((b) => b.text() === 'Delete expense')
    await deleteButton?.trigger('click')
    expect(dialog()?.textContent).toContain("This can't be undone.")
    ;(sheetButton('Delete') as HTMLButtonElement | undefined)?.click()
    await flushPromises()
    expect(del).toHaveBeenCalledWith('/trips/abc/expenses/e1')
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/trips/abc?day=2026-11-06'))
  })

  it('hides edit and delete actions on locked trips', async () => {
    const { wrapper } = await mountDetail(percentSplit, { locked: true })
    expect(text(wrapper)).toContain('This trip is locked, so it is view-only.')
    expect(wrapper.find('a[href="/trips/abc/expenses/e1/edit"]').exists()).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text() === 'Delete expense')).toBe(false)
  })

  it('renders not-found error state for missing expenses', async () => {
    get.mockImplementation((path: string) =>
      path === '/trips/abc' ? Promise.resolve(trip) : Promise.reject(new ApiError(404, 'not_found', 'x')),
    )
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/trips/:tripId', component: stub },
        { path: '/trips/:tripId/expenses/:expenseId', component: ExpenseDetailView },
      ],
    })
    await router.push('/trips/abc/expenses/e1')
    wrapper = mount(ExpenseDetailView, { global: { plugins: [createAppI18n('en'), router] } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe("We couldn't find this expense.")
  })
})
