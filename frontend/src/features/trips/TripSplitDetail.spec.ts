import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import type { Expense } from '@/entities'
import { expense } from '@/features/expenses/expenseFixtures'
import { field } from '@/features/expenses/expenseFormHarness'
import { mockSplit, mountTrip, serve, unmountTrip } from '@/features/trips/splitHarness'
import { ApiError, api } from '@/lib/api'
import { dialog } from '@/lib/domTestHelpers'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const put = vi.mocked(api.put)
const del = vi.mocked(api.delete)

const hotpot = expense(
  { '1': 150_000, '2': 150_000 },
  { id: 'e9', title: 'Hotpot', paid_by: '1', version: 3, spent_on: '2026-11-06', note: 'Tasty' },
)
const coffee = expense({ '1': 20_000, '2': 20_000 }, { id: 'e8', title: 'Coffee', paid_by: '2', spent_on: '2026-11-06' })
const pho = expense({ '1': 100_000, '2': 100_000 }, { id: 'e1', title: 'Pho', paid_by: '1', spent_on: '2026-11-05' })

const pane = (view: VueWrapper) => view.get('.split-detail')
const query = (router: { currentRoute: { value: { query: unknown } } }) => router.currentRoute.value.query
const paneButton = (view: VueWrapper, label: string) =>
  pane(view)
    .findAll('button')
    .find((button) => button.text() === label)

async function confirmDelete(view: VueWrapper) {
  await paneButton(view, 'Delete expense')?.trigger('click')
  const confirm = [...(dialog()?.querySelectorAll('button') ?? [])].find(
    (button) => button.textContent?.trim() === 'Delete',
  )
  ;(confirm as HTMLButtonElement | undefined)?.click()
  await flushPromises()
}

beforeEach(() => {
  get.mockReset()
  put.mockReset()
  del.mockReset()
  Element.prototype.scrollIntoView = vi.fn()
  mockSplit(true)
})

afterEach(() => {
  unmountTrip()
})

describe('default selection', () => {
  it('opens the newest expense and writes it to the URL without adding a history entry', async () => {
    serve({ all: [hotpot, coffee, pho] })
    const { view, router } = await mountTrip()
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e9' })
    expect(pane(view).get('h2').text()).toBe('Hotpot')
    expect(pane(view).text()).toContain('₫300,000')
    expect(pane(view).text()).toContain('Tasty')
    expect(view.get('li button[aria-current="true"]').text()).toContain('Hotpot')
    router.back()
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/trips/abc')
  })

  it('selects rows instead of expanding them', async () => {
    serve({ all: [hotpot, coffee, pho] })
    const { view } = await mountTrip()
    expect(view.find('li button[aria-expanded]').exists()).toBe(false)
    expect(view.findAll('.split-list li > button')).toHaveLength(2)
    expect(view.find('li svg.lucide-chevron-down').exists()).toBe(false)
  })

  it('opens the add form when the trip has no expenses', async () => {
    serve({ all: [] })
    const { view, router } = await mountTrip()
    expect(pane(view).find('form').exists()).toBe(true)
    expect(query(router)).toEqual({})
  })
})

describe('choosing an expense', () => {
  it('shows the tapped expense, marks its row and lets Back return to the previous one', async () => {
    serve({ all: [hotpot, coffee, pho] })
    const { view, router } = await mountTrip()
    await view.findAll('li button')[1]?.trigger('click')
    await flushPromises()
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e8' })
    expect(pane(view).get('h2').text()).toBe('Coffee')
    expect(view.get('li button[aria-current="true"]').text()).toContain('Coffee')
    router.back()
    await flushPromises()
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e9' })
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })

  it('reopens the expense and the day named in the URL', async () => {
    serve({ all: [hotpot, coffee, pho] })
    const { view, router } = await mountTrip('/trips/abc?day=2026-11-05&expense=e1')
    expect(query(router)).toEqual({ day: '2026-11-05', expense: 'e1' })
    expect(pane(view).get('h2').text()).toBe('Pho')
    expect(view.get('[role="tab"][aria-selected="true"]').text()).toBe('Day 1')
    expect(view.get('li button[aria-current="true"]').text()).toContain('Pho')
  })

  it('selects the first expense of another day when its tab is picked', async () => {
    serve({ all: [hotpot, coffee, pho] })
    const { view, router } = await mountTrip()
    await view.findAll('[role="tab"]')[1]?.trigger('click')
    await flushPromises()
    expect(query(router)).toEqual({ day: '2026-11-05', expense: 'e1' })
    expect(pane(view).get('h2').text()).toBe('Pho')
  })

  it('falls back to the newest expense when the one in the URL does not exist', async () => {
    serve({ all: [hotpot, coffee] })
    const { view, router } = await mountTrip('/trips/abc?expense=gone')
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e9' })
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })
})

describe('editing in the pane', () => {
  async function openEdit() {
    const state = { all: [hotpot, coffee] }
    serve(state)
    const mounted = await mountTrip()
    await paneButton(mounted.view, 'Edit expense')?.trigger('click')
    await flushPromises()
    return { ...mounted, state }
  }

  it('opens the form in the pane, keeping the list, and closing returns to the detail', async () => {
    const { view, router } = await openEdit()
    expect(pane(view).find('form').exists()).toBe(true)
    expect(view.find('.split-list li').exists()).toBe(true)
    expect(router.currentRoute.value.path).toBe('/trips/abc')
    await pane(view).get('[aria-label="Close"]').trigger('click')
    expect(pane(view).find('form').exists()).toBe(false)
    expect(pane(view).get('h2').text()).toBe('Hotpot')
  })

  it('saves with the version it read, then shows the new detail and list', async () => {
    const { view, state } = await openEdit()
    put.mockImplementation((_path, body) => {
      const saved = { ...hotpot, ...(body as object), title: 'Seafood hotpot', version: 4 } as Expense
      state.all = [saved, coffee]
      return Promise.resolve(saved)
    })
    await field(view, 'What for').setValue('Seafood hotpot')
    await pane(view).get('form').trigger('submit')
    await flushPromises()
    expect(put).toHaveBeenCalledWith(
      '/trips/abc/expenses/e9',
      expect.objectContaining({ version: 3, title: 'Seafood hotpot' }),
    )
    expect(pane(view).find('form').exists()).toBe(false)
    expect(pane(view).get('h2').text()).toBe('Seafood hotpot')
    expect(view.get('.split-list').text()).toContain('Seafood hotpot')
  })

  it('offers the latest version after a version conflict', async () => {
    const { view } = await openEdit()
    put.mockRejectedValue(new ApiError(409, 'version_conflict', 'Conflict'))
    await pane(view).get('form').trigger('submit')
    await flushPromises()
    expect(pane(view).find('[role="alert"]').exists()).toBe(true)
    expect(pane(view).text()).toContain('Load the latest version')
  })
})

describe('deleting from the pane', () => {
  it('confirms, deletes and moves the selection to the newest expense left', async () => {
    const state = { all: [hotpot, coffee, pho] }
    serve(state)
    del.mockImplementation(() => {
      state.all = [coffee, pho]
      return Promise.resolve(undefined)
    })
    const { view, router } = await mountTrip()
    await confirmDelete(view)
    expect(del).toHaveBeenCalledWith('/trips/abc/expenses/e9')
    expect(query(router)).toEqual({ day: '2026-11-06', expense: 'e8' })
    expect(pane(view).get('h2').text()).toBe('Coffee')
    expect(view.get('.split-list').text()).not.toContain('Hotpot')
  })

  it('opens the add form after the last expense goes', async () => {
    const state = { all: [hotpot] }
    serve(state)
    del.mockImplementation(() => {
      state.all = []
      return Promise.resolve(undefined)
    })
    const { view, router } = await mountTrip()
    await confirmDelete(view)
    expect(query(router)).toEqual({})
    expect(pane(view).find('form').exists()).toBe(true)
  })
})

describe('below the split breakpoint', () => {
  it('keeps rows expanding in place and leaves the URL alone', async () => {
    mockSplit(false)
    serve({ all: [hotpot, coffee] })
    const { view, router } = await mountTrip()
    expect(query(router)).toEqual({})
    expect(view.findAll('li button[aria-expanded="false"]')).toHaveLength(2)
    expect(view.find('li button[aria-current]').exists()).toBe(false)
    expect(view.find('.split-detail h2').exists()).toBe(false)
    await view.get('li button').trigger('click')
    expect(view.get('li button').attributes('aria-expanded')).toBe('true')
    expect(query(router)).toEqual({})
  })
})
