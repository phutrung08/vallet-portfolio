import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { expense } from '@/features/expenses/expenseFixtures'
import { mockSplit, mountTrip, serve, unmountTrip } from '@/features/trips/splitHarness'
import { api } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const hotpot = expense(
  { '1': 150_000, '2': 150_000 },
  { id: 'e9', title: 'Hotpot', paid_by: '1', spent_on: '2026-11-06', category: 'food' },
)
const taxi = expense(
  { '1': 50_000, '2': 50_000 },
  { id: 'e8', title: 'Taxi', paid_by: '2', spent_on: '2026-11-05', category: 'transport' },
)

const pane = (view: VueWrapper) => view.get('.split-detail')
const switchButton = (view: VueWrapper, label: string) =>
  pane(view)
    .findAll('[role="group"] button')
    .find((button) => button.text() === label)
const query = (router: { currentRoute: { value: { query: unknown } } }) => router.currentRoute.value.query

async function openStats(view: VueWrapper) {
  await switchButton(view, 'Stats')?.trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.mocked(api.get).mockReset()
  Element.prototype.scrollIntoView = vi.fn()
  localStorage.clear()
  mockSplit(true)
})

afterEach(unmountTrip)

describe('stats pane', () => {
  it('shows the total, spending by category and who paid how much from the summary and balances endpoints', async () => {
    serve({ all: [hotpot, taxi] })
    const { view, router } = await mountTrip()
    await openStats(view)
    expect(query(router)).toMatchObject({ pane: 'stats' })
    expect(api.get).toHaveBeenCalledWith('/trips/abc/summary', { signal: expect.any(AbortSignal) })
    expect(api.get).toHaveBeenCalledWith('/trips/abc/balances', { signal: expect.any(AbortSignal) })

    const text = pane(view).text()
    expect(text).toContain('₫400,000')
    expect(text).toContain('By category')
    expect(text).toContain('Food')
    expect(text).toContain('75%')
    expect(text).toContain('Transport')
    expect(text).toContain('25%')
    const paid = pane(view).findAll('section').filter((section) => section.text().includes('Who paid how much')).at(-1)
    expect(paid?.findAll('li').map((row) => row.text())).toEqual([
      expect.stringContaining('Alex'),
      expect.stringContaining('Ben'),
    ])
    expect(paid?.text()).toContain('₫300,000')
    expect(paid?.text()).toContain('Share of costs ₫200,000')
    expect(paid?.text()).not.toContain('Former guest')
  })

  it('works on a trip that cannot take an expense, without Add', async () => {
    serve({ all: [hotpot] }, { locked: true })
    const { view } = await mountTrip('/trips/abc?pane=stats')
    expect(pane(view).text()).toContain('By category')
    expect(pane(view).findAll('[role="group"] button').map((button) => button.text())).toEqual(['Details', 'Stats'])
  })

  it('is not offered, and not shown from the URL, on a trip with no expenses', async () => {
    serve({ all: [] })
    const { view } = await mountTrip('/trips/abc?pane=stats')
    expect(pane(view).findAll('[role="group"] button').map((button) => button.text())).toEqual(['Details', 'Add'])
    expect(pane(view).text()).not.toContain('By category')
    expect(pane(view).get('h2').text()).toBe('Add expense')
  })
})

describe('remembering the mode', () => {
  it('opens on Stats next time after Stats was the last choice', async () => {
    serve({ all: [hotpot, taxi] })
    const first = await mountTrip()
    await openStats(first.view)
    unmountTrip()
    mockSplit(true)
    const { view, router } = await mountTrip()
    expect(query(router)).toMatchObject({ pane: 'stats' })
    expect(pane(view).text()).toContain('By category')
    router.back()
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/trips/abc')
  })

  it('goes back to opening on Details after Details is chosen again, or a row is tapped', async () => {
    serve({ all: [hotpot, taxi] })
    const first = await mountTrip()
    await openStats(first.view)
    await first.view.findAll('li button')[0]?.trigger('click')
    await flushPromises()
    expect(localStorage.getItem('vallet.pane')).toBe('details')
    unmountTrip()
    mockSplit(true)
    const { view } = await mountTrip()
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })

  it('does not remember Add', async () => {
    serve({ all: [hotpot, taxi] })
    const first = await mountTrip()
    await switchButton(first.view, 'Add')?.trigger('click')
    await flushPromises()
    unmountTrip()
    mockSplit(true)
    const { view } = await mountTrip()
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })

  it('lets the URL win over the memory', async () => {
    localStorage.setItem('vallet.pane', 'stats')
    serve({ all: [hotpot, taxi] })
    const { view } = await mountTrip('/trips/abc?pane=details')
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })

  it('still opens on Add for a trip with no expenses', async () => {
    localStorage.setItem('vallet.pane', 'stats')
    serve({ all: [] })
    const { view } = await mountTrip()
    expect(pane(view).get('h2').text()).toBe('Add expense')
  })
})
