import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import type { Expense } from '@/entities'
import { expense } from '@/features/expenses/expenseFixtures'
import { field, fillValid } from '@/features/expenses/expenseFormHarness'
import { mockSplit, mountTrip, serve, unmountTrip } from '@/features/trips/splitHarness'
import { api } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const post = vi.mocked(api.post)

const hotpot = expense({ '1': 150_000, '2': 150_000 }, { id: 'e9', title: 'Hotpot', paid_by: '1', spent_on: '2026-11-06' })
const coffee = expense({ '1': 20_000, '2': 20_000 }, { id: 'e8', title: 'Coffee', paid_by: '2', spent_on: '2026-11-06' })
const noodles = (id: string) =>
  expense({ '1': 197_500, '2': 197_500 }, { id, title: 'Noodles', paid_by: '1', spent_on: '2026-11-06' })

const pane = (view: VueWrapper) => view.get('.split-detail')
const query = (router: { currentRoute: { value: { query: unknown } } }) => router.currentRoute.value.query
const switchButton = (view: VueWrapper, label: string) =>
  pane(view)
    .findAll('[role="group"] button')
    .find((button) => button.text() === label)
const addButton = (view: VueWrapper) => view.get('nav button')

async function submit(view: VueWrapper) {
  await fillValid(view)
  await pane(view).get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  vi.mocked(api.get).mockReset()
  post.mockReset()
  Element.prototype.scrollIntoView = vi.fn()
  mockSplit(true)
})

afterEach(unmountTrip)

describe('mode switch', () => {
  it('offers Details, Add and Stats, starting on Details with the URL untouched', async () => {
    serve({ all: [hotpot, coffee] })
    const { view, router } = await mountTrip()
    const buttons = pane(view).findAll('[role="group"] button')
    expect(buttons.map((button) => button.text())).toEqual(['Details', 'Add', 'Stats'])
    expect(buttons[0]?.attributes('aria-pressed')).toBe('true')
    expect(pane(view).get('h2').text()).toBe('Hotpot')
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e9' })
  })

  it('opens the add form with the amount focused, keeping the list and the selection', async () => {
    serve({ all: [hotpot, coffee] })
    const { view, router } = await mountTrip()
    await switchButton(view, 'Add')?.trigger('click')
    await flushPromises()
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e9', pane: 'add' })
    expect(pane(view).get('h2').text()).toBe('Add expense')
    expect(document.activeElement).toBe(field(view, 'Amount').element)
    expect(view.get('.split-list').text()).toContain('Coffee')
  })

  it('returns to Details from the switch, the close button and Back', async () => {
    serve({ all: [hotpot, coffee] })
    const { view, router } = await mountTrip()
    await switchButton(view, 'Add')?.trigger('click')
    await flushPromises()
    await switchButton(view, 'Details')?.trigger('click')
    await flushPromises()
    expect(pane(view).get('h2').text()).toBe('Hotpot')
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e9' })
    await switchButton(view, 'Add')?.trigger('click')
    await flushPromises()
    await pane(view).get('[aria-label="Close"]').trigger('click')
    await flushPromises()
    expect(pane(view).get('h2').text()).toBe('Hotpot')
    await switchButton(view, 'Add')?.trigger('click')
    await flushPromises()
    router.back()
    await flushPromises()
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })

  it('shows Details again when a row is tapped in Add mode', async () => {
    serve({ all: [hotpot, coffee] })
    const { view, router } = await mountTrip('/trips/abc?day=2026-11-06&expense=e9&pane=add')
    expect(pane(view).get('h2').text()).toBe('Add expense')
    await view.findAll('li button')[1]?.trigger('click')
    await flushPromises()
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e8' })
    expect(pane(view).get('h2').text()).toBe('Coffee')
  })
})

describe('the + button', () => {
  it('switches the right pane to Add on split screens', async () => {
    serve({ all: [hotpot] })
    const { view, router } = await mountTrip()
    await addButton(view).trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/trips/abc')
    expect(query(router)).toMatchObject({ pane: 'add' })
    expect(pane(view).get('h2').text()).toBe('Add expense')
  })

  it('keeps the full-screen form on a phone', async () => {
    mockSplit(false)
    serve({ all: [hotpot] })
    const { view, router } = await mountTrip()
    await addButton(view).trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/trips/abc/expenses/new')
  })
})

describe('saving from the pane', () => {
  it('reloads the list, selects the new expense and goes back to Details', async () => {
    const state = { all: [hotpot] }
    serve(state)
    const { view, router } = await mountTrip('/trips/abc?pane=add')
    post.mockImplementation(() => {
      state.all = [noodles('e10'), hotpot]
      return Promise.resolve(noodles('e10'))
    })
    await submit(view)
    expect(post).toHaveBeenCalledWith(
      '/trips/abc/expenses',
      expect.objectContaining({ title: 'Noodles', amount: 395_000 }),
      expect.anything(),
    )
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e10' })
    expect(pane(view).get('h2').text()).toBe('Noodles')
    expect(view.get('.split-list').text()).toContain('Noodles')
  })
})

describe('trips with no expenses', () => {
  it('open on the add form without a close button, and Details shows the hint', async () => {
    serve({ all: [] })
    const { view, router } = await mountTrip()
    expect(pane(view).get('h2').text()).toBe('Add expense')
    expect(pane(view).find('[aria-label="Close"]').exists()).toBe(false)
    expect(query(router)).toEqual({})
    await switchButton(view, 'Details')?.trigger('click')
    await flushPromises()
    expect(query(router)).toEqual({ pane: 'details' })
    expect(pane(view).text()).toContain('No expenses yet')
  })

  it('lead the first saved expense straight to its detail', async () => {
    const state = { all: [] as Expense[] }
    serve(state)
    const { view, router } = await mountTrip()
    post.mockImplementation(() => {
      state.all = [noodles('e1')]
      return Promise.resolve(noodles('e1'))
    })
    await submit(view)
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e1' })
    expect(pane(view).get('h2').text()).toBe('Noodles')
  })
})

describe('trips that cannot take an expense', () => {
  it.each([{ locked: true }, { closed: true }])('hide Add and its URL for %j', async (flag) => {
    serve({ all: [hotpot] }, flag)
    const { view } = await mountTrip('/trips/abc?pane=add')
    expect(pane(view).findAll('[role="group"] button').map((button) => button.text())).toEqual(['Details', 'Stats'])
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })
})
