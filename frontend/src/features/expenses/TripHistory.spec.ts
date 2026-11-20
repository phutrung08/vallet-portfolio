import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { DaySummary } from '@/entities'
import TripHistory from '@/features/expenses/TripHistory.vue'
import { trip } from '@/features/trips/tripFixtures'
import { api } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)

const days: DaySummary[] = [
  { date: '2026-11-07', count: 9, total: 1_500_000 },
  { date: '2026-11-06', count: 2, total: 300_000 },
  { date: '2026-11-05', count: 1, total: 200_000 },
]
const scrollIntoView = vi.fn()

beforeEach(() => {
  scrollIntoView.mockReset()
  get.mockReset()
  get.mockResolvedValue({ expenses: [] })
  Element.prototype.scrollIntoView = scrollIntoView
})

async function mountHistory(
  props: { days?: DaySummary[]; today?: string; startsOn?: string | null } = {},
  path = '/trips/abc',
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }],
  })
  await router.push(path)
  const wrapper = mount(TripHistory, {
    props: {
      trip: {
        ...trip,
        starts_on: props.startsOn === undefined ? trip.starts_on : props.startsOn,
      },
      days: props.days ?? days,
      today: props.today ?? '2026-11-20',
    },
    attachTo: document.body,
    global: { plugins: [createAppI18n('en'), router] },
  })
  await flushPromises()
  return { wrapper, router }
}

const tabs = (wrapper: Awaited<ReturnType<typeof mountHistory>>['wrapper']) =>
  wrapper.findAll('[role="tab"]')

describe('day tabs', () => {
  it('labels days relative to trip start date, newest first', async () => {
    const { wrapper } = await mountHistory()
    expect(tabs(wrapper).map((tab) => tab.text())).toEqual(['Day 3', 'Day 2', 'Day 1'])
  })

  it('uses short calendar dates without a start date or before it', async () => {
    const without = await mountHistory({ startsOn: null })
    expect(tabs(without.wrapper).map((tab) => tab.text())).toEqual(['11/7', '11/6', '11/5'])
    const before = await mountHistory({ startsOn: '2026-11-06' })
    expect(tabs(before.wrapper).map((tab) => tab.text())).toEqual(['Day 2', 'Day 1', '11/5'])
  })

  it('selects newest day by default and today when recorded', async () => {
    const newest = await mountHistory()
    expect(tabs(newest.wrapper).map((tab) => tab.attributes('aria-selected'))).toEqual([
      'true',
      'false',
      'false',
    ])
    const today = await mountHistory({ today: '2026-11-06' })
    expect(tabs(today.wrapper).map((tab) => tab.attributes('aria-selected'))).toEqual([
      'false',
      'true',
      'false',
    ])
  })

  it('honors valid ?day= query param and falls back otherwise', async () => {
    const listed = await mountHistory({}, '/trips/abc?day=2026-11-05')
    expect(tabs(listed.wrapper)[2]?.attributes('aria-selected')).toBe('true')
    const unknown = await mountHistory({}, '/trips/abc?day=2026-12-01')
    expect(tabs(unknown.wrapper)[0]?.attributes('aria-selected')).toBe('true')
  })

  it('uses roving tabindex across tablist and links ARIA panel attributes', async () => {
    const { wrapper } = await mountHistory()
    expect(wrapper.find('[role="tablist"]').exists()).toBe(true)
    expect(tabs(wrapper).map((tab) => tab.attributes('tabindex'))).toEqual(['0', '-1', '-1'])
    const panel = wrapper.get('[role="tabpanel"]')
    expect(panel.attributes('aria-labelledby')).toBe(tabs(wrapper)[0]?.attributes('id'))
    expect(tabs(wrapper)[0]?.attributes('aria-controls')).toBe(panel.attributes('id'))
  })

  it('navigates tabs with arrow keys, Home, and End', async () => {
    const { wrapper } = await mountHistory()
    const selectedDate = () =>
      tabs(wrapper).findIndex((tab) => tab.attributes('aria-selected') === 'true')
    ;(tabs(wrapper)[0]?.element as HTMLElement).focus()
    await tabs(wrapper)[0]?.trigger('keydown', { key: 'ArrowLeft' })
    expect(selectedDate()).toBe(0)
    await tabs(wrapper)[0]?.trigger('keydown', { key: 'ArrowRight' })
    expect(selectedDate()).toBe(1)
    await flushPromises()
    expect(document.activeElement).toBe(tabs(wrapper)[1]?.element)
    await tabs(wrapper)[1]?.trigger('keydown', { key: 'End' })
    expect(selectedDate()).toBe(2)
    await tabs(wrapper)[2]?.trigger('keydown', { key: 'Home' })
    expect(selectedDate()).toBe(0)
  })

  it('scrolls newly selected tab into view', async () => {
    const { wrapper } = await mountHistory()
    expect(scrollIntoView).toHaveBeenCalled()
    scrollIntoView.mockClear()
    await tabs(wrapper)[2]?.trigger('click')
    await flushPromises()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
  })

  it('displays date, expense count, and formatted total for the active day', async () => {
    const { wrapper } = await mountHistory()
    const [label, total] = wrapper.findAll('[role="tabpanel"] p span')
    expect(label?.text()).toBe('11/7 · 9 expenses')
    expect(total?.text()).toContain('1,500,000')
    await tabs(wrapper)[1]?.trigger('click')
    expect(wrapper.get('[role="tabpanel"] p').text()).toContain('11/6 · 2 expenses')
  })
})

describe('day cache behavior', () => {
  it('fetches each day once regardless of how many times tabs are revisited', async () => {
    const { wrapper } = await mountHistory()
    expect(get.mock.calls.map(([path]) => path)).toEqual(['/trips/abc/expenses?day=2026-11-07'])
    await tabs(wrapper)[1]?.trigger('click')
    await flushPromises()
    await tabs(wrapper)[0]?.trigger('click')
    await flushPromises()
    await tabs(wrapper)[1]?.trigger('click')
    await flushPromises()
    expect(get.mock.calls.map(([path]) => path)).toEqual([
      '/trips/abc/expenses?day=2026-11-07',
      '/trips/abc/expenses?day=2026-11-06',
    ])
  })
})

describe('empty trip history', () => {
  it('shows empty state with CTA button to add first expense', async () => {
    const { wrapper, router } = await mountHistory({ days: [] })
    expect(wrapper.find('[role="tablist"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('No expenses yet')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/trips/abc/expenses/new')
  })
})
