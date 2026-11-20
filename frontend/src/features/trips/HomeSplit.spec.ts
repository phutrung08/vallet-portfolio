import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { TripSummary } from '@/entities'
import HomeView from '@/features/trips/HomeView.vue'
import { mockSplit, splitTestRoutes } from '@/features/trips/splitHarness'
import { api } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)
const TODAY = new Date(2026, 10, 6)

const summary = (id: string, name: string): TripSummary => ({
  id,
  name,
  currency: 'VND',
  starts_on: '2026-11-05',
  ends_on: '2026-11-08',
  uses_fund: false,
  closed: false,
  member_count: 3,
  me: `${id}-me`,
})
const trips = [summary('t1', 'Da Lat'), summary('t2', 'Phu Quoc')]

function serve(list: TripSummary[]) {
  get.mockImplementation((path: string) => {
    if (path === '/trips') return Promise.resolve({ trips: list })
    const id = /^\/trips\/([^/]+)\//.exec(path)?.[1] ?? ''
    if (path.endsWith('/expenses/days')) return Promise.resolve({ days: [{ date: '2026-11-06', count: 2, total: 500_000 }] })
    if (path.endsWith('/balances')) {
      const standing = {
        member_id: `${id}-me`,
        paid: 500_000,
        contributed: 0,
        share: 200_000,
        sent: 0,
        received: 0,
        net: 300_000,
        removed: false,
      }
      return Promise.resolve({ currency: 'VND', fund: { holder_id: null, remaining: 0 }, members: [standing], transfers: [] })
    }
    const expense = (n: number) => ({ id: `${id}-e${n}`, title: `Meal ${id} ${n}`, amount: 250_000, category: 'food' })
    return Promise.resolve({ expenses: [expense(1), expense(2)] })
  })
}

async function mountHome(path = '/', list = trips) {
  serve(list)
  const router = createRouter({ history: createMemoryHistory(), routes: splitTestRoutes })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(HomeView, {
    props: { now: () => TODAY },
    global: { plugins: [createAppI18n('en'), router] },
  })
  await flushPromises()
  return { wrapper, router }
}

const current = (wrapper: Awaited<ReturnType<typeof mountHome>>['wrapper']) =>
  wrapper.findAll('.split-list [aria-current="true"]').map((card) => card.text())
const requests = () => get.mock.calls.map(([path]) => path)

beforeEach(() => {
  get.mockReset()
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HomeView on a split screen', () => {
  it('picks the first trip by replacing the URL and shows its overview', async () => {
    mockSplit(true)
    const { wrapper, router } = await mountHome()
    expect(router.currentRoute.value.query.trip).toBe('t1')
    expect(current(wrapper)[0]).toContain('Da Lat')
    const detail = wrapper.get('.split-detail')
    expect(detail.get('h2').text()).toContain('Da Lat')
    expect(detail.text()).toContain('₫500,000')
    expect(detail.text()).toContain('+₫300,000')
    expect(detail.text()).toContain('Meal t1 1')
  })

  it('loads the overview only for the selected trip', async () => {
    mockSplit(true)
    await mountHome()
    expect(requests().filter((path) => String(path).includes('/t2/'))).toEqual([])
  })

  it('pushes another trip on tap, then opens the selected one on a second tap', async () => {
    mockSplit(true)
    const { wrapper, router } = await mountHome()
    await wrapper.findAll('.split-list ul button')[1]?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.trip).toBe('t2')
    expect(wrapper.get('.split-detail h2').text()).toContain('Phu Quoc')
    await wrapper.findAll('.split-list ul button')[1]?.trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/t2'))
  })

  it('opens the trip from the overview button', async () => {
    mockSplit(true)
    const { wrapper, router } = await mountHome()
    await wrapper.get('.split-detail button').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/t1'))
  })

  it('explains how it works in the right pane when there are no trips', async () => {
    mockSplit(true)
    const { wrapper } = await mountHome('/', [])
    expect(wrapper.get('.split-detail').text()).toContain('View a sample trip')
    expect(wrapper.findAll('.split-list button').map((b) => b.text())).toContain('Create a trip')
    expect(wrapper.findAll('h1')).toHaveLength(1)
  })

  it('leaves phones alone: links, no overview, URL untouched', async () => {
    mockSplit(false)
    const { wrapper, router } = await mountHome()
    expect(router.currentRoute.value.query.trip).toBeUndefined()
    expect(wrapper.findAll('.split-list ul a').map((a) => a.attributes('href'))).toEqual(['/trips/t1', '/trips/t2'])
    expect(wrapper.get('.split-detail').text()).toBe('')
    expect(requests()).toEqual(['/trips'])
  })
})
