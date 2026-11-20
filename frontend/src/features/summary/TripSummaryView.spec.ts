import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import type { TripSpendSummary } from '@/entities'
import TripSummaryView from '@/features/summary/TripSummaryView.vue'
import { trip } from '@/features/trips/tripFixtures'
import { api } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const stub = defineComponent({ template: '<div />' })

const routes: RouteRecordRaw[] = [
  { path: '/trips/:tripId/summary', component: TripSummaryView },
  { path: '/trips/:tripId', component: stub },
  { path: '/trips/:tripId/balances', component: stub },
  { path: '/trips/:tripId/members', component: stub },
  { path: '/trips/:tripId/expenses/new', component: stub },
  { path: '/settings', component: stub },
  { path: '/', component: stub },
]

const get = vi.mocked(api.get)
let wrapper: VueWrapper | undefined

const sampleSummary: TripSpendSummary = {
  currency: 'VND',
  total: 400_000,
  expense_count: 3,
  active_member_count: 2,
  day_count: 2,
  per_person: 200_000,
  per_day: 200_000,
  categories: [
    { category: 'food', count: 1, amount: 200_000, percent: 50 },
    { category: 'lodging', count: 1, amount: 100_000, percent: 25 },
    { category: 'transport', count: 1, amount: 100_000, percent: 25 },
  ],
  payers: [],
  days: [
    { date: '2026-11-06', count: 2, total: 300_000 },
    { date: '2026-11-05', count: 1, total: 100_000 },
  ],
}

const emptySummary: TripSpendSummary = {
  currency: 'VND',
  total: 0,
  expense_count: 0,
  active_member_count: 2,
  day_count: 0,
  per_person: 0,
  per_day: 0,
  categories: [],
  payers: [],
  days: [],
}

function serve(summaryOut: TripSpendSummary = sampleSummary) {
  get.mockImplementation((path: string) => {
    if (path === '/trips/abc') return Promise.resolve(trip)
    if (path === '/trips/abc/summary') return Promise.resolve(summaryOut)
    return Promise.reject(new Error(`unexpected GET ${path}`))
  })
}

async function mountSummary() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/trips/abc/summary')
  await router.isReady()
  wrapper = mount(RouterView, { global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  get.mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('TripSummaryView', () => {
  it('shows the total and expense count from the summary API endpoint', async () => {
    serve()
    const view = await mountSummary()
    expect(view.get('h1').text()).toBe('Trip summary')
    expect(view.text()).toContain('₫400,000')
    expect(view.text()).toContain('3 expenses')
  })

  it('fetches only /trips/abc and /trips/abc/summary without N+1 day expense calls', async () => {
    serve()
    await mountSummary()
    expect(get.mock.calls.map(([path]) => path).sort()).toEqual(['/trips/abc', '/trips/abc/summary'])
    expect(get).toHaveBeenCalledWith('/trips/abc/summary', { signal: expect.any(AbortSignal) })
  })

  it('lists categories biggest first with amounts and percents summing to 100', async () => {
    serve()
    const view = await mountSummary()
    const rows = view.findAll('section li').map((row) => row.text())
    expect(rows).toHaveLength(3)
    expect(rows[0]).toContain('Food')
    expect(rows[0]).toContain('₫200,000')
    expect(rows[0]).toContain('50%')
    expect(rows[1]).toContain('Lodging')
    expect(rows[1]).toContain('25%')
    expect(rows[2]).toContain('Transport')
    expect(rows[2]).toContain('25%')
    const bar = view.get('[role="img"]')
    expect(bar.attributes('aria-label')).toBe('Food 50%, Lodging 25%, Transport 25%')
    const widths = bar.findAll('div').map((segment) => segment.attributes('style'))
    expect(widths).toEqual(['width: 50%;', 'width: 25%;', 'width: 25%;'])
  })

  it('shows the average per active member and per day', async () => {
    serve()
    const view = await mountSummary()
    const tiles = view.findAll('.grid > *').map((tile) => tile.text())
    expect(tiles[0]).toContain('~₫200,000')
    expect(tiles[1]).toContain('Per day')
    expect(tiles[1]).toContain('~₫200,000')
  })

  it('renders empty-state copy for a trip without expenses', async () => {
    serve(emptySummary)
    const view = await mountSummary()
    expect(view.text()).toContain('No expenses yet')
    expect(view.find('[role="img"]').exists()).toBe(false)
  })
})
