import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import type { Expense, SplitMode, TripDetail } from '@/entities'
import { expense } from '@/features/expenses/expenseFixtures'
import { field, mountExpenseForm } from '@/features/expenses/expenseFormHarness'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { dialog } from '@/lib/domTestHelpers'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const put = vi.mocked(api.put)
const del = vi.mocked(api.delete)
// '3' left the trip yet participates in the edited expense; '5' left and is not attached so stays hidden.
const tripWithLeavers: TripDetail = {
  ...trip,
  members: [...trip.members, { id: '5', display_name: 'Owen', position: 3, removed: true }],
}
let wrapper: VueWrapper | undefined

function stored(
  mode: SplitMode,
  weights: Record<string, number>,
  amounts: Record<string, number>,
  overrides: Partial<Expense> = {},
) {
  return expense(amounts, {
    id: 'e1',
    title: 'Hotpot',
    category: 'food',
    spent_on: '2026-11-06',
    paid_by: '1',
    split_mode: mode,
    shares: Object.entries(weights).map(([member_id, weight]) => ({
      member_id,
      weight,
      amount: amounts[member_id] ?? 0,
    })),
    note: 'Corner stall',
    place: 'Da Lat Market',
    version: 3,
    ...overrides,
  })
}

function serve(...versions: Expense[]) {
  let call = 0
  get.mockImplementation((path: string) => {
    if (path === '/trips/abc') return Promise.resolve(tripWithLeavers)
    if (path === '/trips/abc/expenses/e1') return Promise.resolve(versions[Math.min(call++, versions.length - 1)])
    return Promise.reject(new Error(`unexpected GET ${path}`))
  })
}

async function mountEdit(...versions: Expense[]) {
  serve(...versions)
  const mounted = await mountExpenseForm('/trips/abc/expenses/e1/edit')
  wrapper = mounted.wrapper
  return mounted
}

const tiles = (form: VueWrapper) => form.findAll('button[aria-pressed]').map((tile) => tile.text().replaceAll('\u00a0', ' '))
const sheetButton = (text: string) =>
  [...(dialog()?.querySelectorAll('button') ?? [])].find((btn) => btn.textContent?.trim() === text)
const button = (form: VueWrapper, text: string) => {
  const found = form.findAll('button').find((item) => item.text() === text)
  if (!found) throw new Error(`No button ${text}`)
  return found
}

beforeEach(() => {
  get.mockReset()
  put.mockReset().mockResolvedValue({ id: 'e1', spent_on: '2026-11-07' })
  del.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('pre-filling edit form', () => {
  it('populates fields, expands note/place section, and displays Edit heading', async () => {
    const { wrapper } = await mountEdit(stored('equal', { '1': 1, '3': 1 }, { '1': 50_000, '3': 50_000 }))
    expect(wrapper.get('h1').text()).toBe('Edit expense')
    expect(field(wrapper, 'Amount').element).toHaveProperty('value', '100,000')
    expect(field(wrapper, 'What for').element).toHaveProperty('value', 'Hotpot')
    expect(field(wrapper, 'Date').element).toHaveProperty('value', '2026-11-06')
    expect(field(wrapper, 'Note').element).toHaveProperty('value', 'Corner stall')
    expect(field(wrapper, 'Place').element).toHaveProperty('value', 'Da Lat Market')
    expect(wrapper.get('input[value="equal"]').element).toHaveProperty('checked', true)
  })

  it('keeps former member already on expense while hiding unrelated removed members', async () => {
    const { wrapper } = await mountEdit(stored('equal', { '1': 1, '3': 1 }, { '1': 50_000, '3': 50_000 }))
    expect(tiles(wrapper)).toEqual(['AAlex₫50,000', 'BBenOut', 'FFormer guestleft₫50,000'])
    expect(wrapper.text()).not.toContain('Owen')
    await wrapper.get('button[aria-haspopup="dialog"]').trigger('click')
    expect(dialog()?.textContent).toContain('Former guest (left)')
    expect(dialog()?.textContent).not.toContain('Owen')
  })

  it.each([
    ['shares', { '1': 2, '2': 1 }, { '1': 200_000, '2': 100_000 }, ['AAlex₫200,000', 'BBen₫100,000']],
    ['percent', { '1': 6_000, '2': 4_000 }, { '1': 180_000, '2': 120_000 }, ['AAlex₫180,000', 'BBen₫120,000']],
    ['exact', { '1': 250_000, '2': 50_000 }, { '1': 250_000, '2': 50_000 }, ['AAlex₫250,000', 'BBen₫50,000']],
  ] as const)('restores %s inputs and preview shares', async (mode, weights, amounts, expected) => {
    const { wrapper } = await mountEdit(stored(mode, weights, amounts))
    expect(wrapper.get(`input[value="${mode}"]`).element).toHaveProperty('checked', true)
    expect(tiles(wrapper).slice(0, 2)).toEqual(expected)
    if (mode === 'percent') expect(field(wrapper, "Alex's percent").element).toHaveProperty('value', '60.00')
    if (mode === 'exact') expect(field(wrapper, "Ben's amount").element).toHaveProperty('value', '50,000')
    if (mode === 'shares') expect(wrapper.findAll('[aria-live="polite"]').map((n) => n.text())).toEqual(['2', '1'])
  })
})

describe('saving expense edits', () => {
  it('sends PUT payload with version and navigates back to saved day', async () => {
    const { wrapper, router } = await mountEdit(stored('percent', { '1': 6_000, '3': 4_000 }, { '1': 60_000, '3': 40_000 }))
    await field(wrapper, 'What for').setValue('Basil hotpot')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(put).toHaveBeenCalledWith('/trips/abc/expenses/e1', {
      title: 'Basil hotpot',
      amount: 100_000,
      category: 'food',
      spent_on: '2026-11-06',
      paid_by: '1',
      split: { mode: 'percent', basis_points: { '1': 6_000, '3': 4_000 } },
      note: 'Corner stall',
      place: 'Da Lat Market',
      version: 3,
    })
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/trips/abc?day=2026-11-07'))
  })

  it('allows toggling a former participant off and back on', async () => {
    const { wrapper } = await mountEdit(stored('equal', { '1': 1, '3': 1 }, { '1': 50_000, '3': 50_000 }))
    const leaver = () => wrapper.findAll('button[aria-pressed]')[2]
    await leaver()?.trigger('click')
    await leaver()?.trigger('click')
    await wrapper.get('form').trigger('submit')
    expect(put.mock.calls[0]?.[1]).toMatchObject({ split: { mode: 'equal', participants: ['1', '3'] } })
  })

  it('prompts confirmation before reloading latest version after 409 version_conflict', async () => {
    put.mockRejectedValueOnce(new ApiError(409, 'version_conflict', 'x'))
    const latest = stored('equal', { '1': 1, '2': 1 }, { '1': 60_000, '2': 60_000 }, { title: 'Beef stew', version: 4 })
    const { wrapper } = await mountEdit(stored('equal', { '1': 1 }, { '1': 100_000 }), latest)
    await field(wrapper, 'What for').setValue('My draft')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Someone else just changed this expense')

    await button(wrapper, 'Load the latest version').trigger('click')
    expect(dialog()?.textContent).toContain('Discard your changes?')
    sheetButton('Cancel')?.click()
    await flushPromises()
    expect(field(wrapper, 'What for').element).toHaveProperty('value', 'My draft')

    await button(wrapper, 'Load the latest version').trigger('click')
    sheetButton('Load the latest version')?.click()
    await flushPromises()
    expect(field(wrapper, 'What for').element).toHaveProperty('value', 'Beef stew')
    await wrapper.get('form').trigger('submit')
    expect(put.mock.calls[1]?.[1]).toMatchObject({ title: 'Beef stew', version: 4 })
  })
})

describe('deleting from edit view', () => {
  it('asks confirmation inside dialog before deleting and redirecting', async () => {
    const { wrapper, router } = await mountEdit(stored('equal', { '1': 1 }, { '1': 100_000 }))
    await button(wrapper, 'Delete expense').trigger('click')
    expect(dialog()?.textContent).toContain('Delete this expense?')
    expect(dialog()?.textContent).toContain("This can't be undone.")
    expect(del).not.toHaveBeenCalled()
    sheetButton('Delete')?.click()
    await flushPromises()
    expect(del).toHaveBeenCalledWith('/trips/abc/expenses/e1')
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/trips/abc?day=2026-11-06'))
  })

  it('keeps dialog open showing error if delete fails', async () => {
    del.mockRejectedValueOnce(new ApiError(0, 'network_error', 'x'))
    const { wrapper } = await mountEdit(stored('equal', { '1': 1 }, { '1': 100_000 }))
    await button(wrapper, 'Delete expense').trigger('click')
    sheetButton('Delete')?.click()
    await flushPromises()
    expect(dialog()?.textContent).toContain('No connection')
  })
})

describe('edit view boundary states', () => {
  it('renders not-found notice when target expense does not exist', async () => {
    get.mockImplementation((path: string) =>
      path === '/trips/abc' ? Promise.resolve(trip) : Promise.reject(new ApiError(404, 'not_found', 'x')),
    )
    wrapper = (await mountExpenseForm('/trips/abc/expenses/e1/edit')).wrapper
    expect(wrapper.get('[role="alert"]').text()).toBe("We couldn't find this expense.")
  })

  it('keeps optional note and place collapsed when creating a new expense', async () => {
    get.mockResolvedValue(trip)
    wrapper = (await mountExpenseForm('/trips/abc/expenses/new')).wrapper
    const toggle = button(wrapper, 'Add a note or place')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(field(wrapper, 'Note').isVisible()).toBe(false)
    await toggle.trigger('click')
    expect(field(wrapper, 'Note').isVisible()).toBe(true)
    expect(wrapper.text()).not.toContain('Delete expense')
  })
})
