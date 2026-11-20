import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import { expense } from '@/features/expenses/expenseFixtures'
import { splitTestRoutes } from '@/features/trips/splitHarness'
import { days, respond, trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { dialog } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const del = vi.mocked(api.delete)
let mounted: VueWrapper | undefined

async function mountTrip() {
  const router = createRouter({ history: createMemoryHistory(), routes: splitTestRoutes })
  await router.push('/trips/abc')
  await router.isReady()
  mounted = mount(RouterView, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return { wrapper: mounted, router }
}

const fundTrip = { fund_holder_id: '1' }

beforeEach(() => {
  get.mockReset()
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  mounted?.unmount()
  mounted = undefined
  document.body.innerHTML = ''
})

describe('TripView header and navigation', () => {
  it('shows the name, back and share links, and the bottom nav', async () => {
    get.mockImplementation(respond())
    const { wrapper } = await mountTrip()
    expect(wrapper.get('h1').text()).toBe('Da Lat')
    const hrefs = wrapper.findAll('a').map((link) => link.attributes('href'))
    expect(hrefs[0]).toBe('/')
    expect(wrapper.get('[aria-label="Share trip"]').attributes('href')).toBe('/trips/abc/members')
    const nav = wrapper.get('nav')
    expect(nav.findAll('a').map((link) => link.attributes('href'))).toEqual([
      '/trips/abc',
      '/trips/abc/balances',
      '/trips/abc/members',
      '/settings',
    ])
  })

  it('navigates to the new expense route from the add button', async () => {
    get.mockImplementation(respond())
    const { wrapper, router } = await mountTrip()
    await wrapper.get('nav button').trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/abc/expenses/new'))
  })

  it('shows the not-found message without retry or nav on 404', async () => {
    get.mockRejectedValue(new ApiError(404, 'not_found', 'Not Found'))
    const { wrapper } = await mountTrip()
    expect(wrapper.get('[role="alert"]').text()).toBe("We couldn't find this trip.")
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('offers a retry on a network error', async () => {
    get.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    get.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    const { wrapper } = await mountTrip()
    expect(wrapper.get('[role="alert"]').text()).toContain('No connection')
    get.mockImplementation(respond())
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Da Lat')
  })
})

describe('deleting from an expense row', () => {
  const hotpot = expense({ '1': 150_000, '2': 150_000 }, { id: 'e9', title: 'Hotpot', spent_on: '2026-11-06' })

  function serve(state: { deleted: boolean }) {
    get.mockImplementation((path: string) => {
      if (path === '/trips/abc') return Promise.resolve(trip)
      if (path === '/trips/abc/expenses/days') {
        const newest = state.deleted ? { ...days[0]!, count: 1, total: 0 } : days[0]!
        return Promise.resolve({ days: [newest, days[1]!] })
      }
      if (path === '/trips/abc/expenses?day=2026-11-06') return Promise.resolve({ expenses: state.deleted ? [] : [hotpot] })
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
  }

  it('confirms, deletes, then reloads the summary and the day in place', async () => {
    const state = { deleted: false }
    serve(state)
    del.mockReset().mockImplementation(() => {
      state.deleted = true
      return Promise.resolve(undefined)
    })
    const { wrapper } = await mountTrip()
    await wrapper.get('li > button').trigger('click')
    await wrapper.get('[aria-label="Delete expense"]').trigger('click')
    const sheet = dialog()
    expect(sheet?.textContent).toContain('Delete this expense?')
    expect(sheet?.textContent).toContain("This can't be undone.")
    const cancel = [...(sheet?.querySelectorAll('button') ?? [])].find((b) => b.textContent?.trim() === 'Cancel')
    cancel?.click()
    await flushPromises()
    expect(del).not.toHaveBeenCalled()

    await wrapper.get('[aria-label="Delete expense"]').trigger('click')
    const confirm = [...(dialog()?.querySelectorAll('button') ?? [])].find((b) => b.textContent?.trim() === 'Delete')
    ;(confirm as HTMLButtonElement | undefined)?.click()
    await flushPromises()
    expect(del).toHaveBeenCalledWith('/trips/abc/expenses/e9')
    const calls = get.mock.calls.map(([path]) => path)
    expect(calls.filter((path) => path === '/trips/abc/expenses/days')).toHaveLength(2)
    expect(calls.filter((path) => path === '/trips/abc/expenses?day=2026-11-06')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('Hotpot')
    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toBe('Day 2')
    expect(wrapper.get('main').text()).toContain('Spent')
  })
})

describe('day tabs on the trip page', () => {
  it('lists the days under the summary, newest first', async () => {
    get.mockImplementation(respond())
    const { wrapper } = await mountTrip()
    expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).toEqual(['Day 2', 'Day 1'])
  })
})

describe('TripSummaryCard', () => {
  it('shows the spent total for a trip without a fund', async () => {
    get.mockImplementation(respond())
    const { wrapper } = await mountTrip()
    const text = wrapper.get('main').text()
    expect(text).toContain('11/5 – 11/8 · 2 people')
    expect(text).toContain('Spent')
    expect(text).toContain('₫500,000')
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(false)
    expect(wrapper.find('a[href="/trips/abc/fund"]').exists()).toBe(false)
  })

  it('shows the fund remaining, progress and totals for a fund trip', async () => {
    const fund = { holder_id: '1', contributed: 2_000_000, spent: 500_000, remaining: 1_500_000 }
    get.mockImplementation(respond(fundTrip, fund))
    const { wrapper } = await mountTrip()
    const text = wrapper.get('main').text()
    expect(text).toContain('Fund left')
    expect(text).toContain('₫1,500,000')
    expect(text).toContain('Paid in ₫2,000,000')
    expect(text).toContain('Spent ₫500,000')
    expect(text).not.toContain('Fund is overdrawn')
    const bar = wrapper.get('[role="progressbar"]')
    expect(bar.attributes('aria-label')).toBe('25% of the fund spent')
    expect(bar.attributes('aria-valuenow')).toBe('25')
    expect(wrapper.get('a[href="/trips/abc/fund"]').text()).toBe('Group fund')
  })

  it('caps the bar at 100% and flags a negative fund', async () => {
    const fund = { holder_id: '1', contributed: 1_000_000, spent: 1_300_000, remaining: -300_000 }
    get.mockImplementation(respond(fundTrip, fund))
    const { wrapper } = await mountTrip()
    expect(wrapper.get('main').text()).toContain('Fund is overdrawn')
    expect(wrapper.get('main').text()).toMatch(/-₫300,000/)
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('100')
  })

  it('shows closed and locked pills', async () => {
    get.mockImplementation(respond({ closed: true, locked: true }))
    const { wrapper } = await mountTrip()
    expect(wrapper.get('main').text()).toContain('Settled')
    expect(wrapper.get('main').text()).toContain('Locked')
  })

  it('shows no pills for an open trip', async () => {
    get.mockImplementation(respond())
    const { wrapper } = await mountTrip()
    expect(wrapper.get('main').text()).not.toMatch(/Settled|Locked/)
  })
})

describe('TripView refresh', () => {
  it('fetches the trip, its days and the shown day again from the header button', async () => {
    get.mockImplementation(respond())
    const { wrapper } = await mountTrip()
    const paths = () => get.mock.calls.map(([path]) => path)
    const before = paths().length
    await wrapper.get('button[aria-label="Refresh"]').trigger('click')
    await flushPromises()
    const again = paths().slice(before)
    expect(again).toContain('/trips/abc')
    expect(again).toContain('/trips/abc/expenses/days')
    expect(again.some((path) => String(path).startsWith('/trips/abc/expenses?day='))).toBe(true)
    expect(wrapper.get('h1').text()).toBe('Da Lat')
  })
})
