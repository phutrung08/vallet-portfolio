import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Expense } from '@/entities'
import ExpenseList from '@/features/expenses/ExpenseList.vue'
import { expense, members } from '@/features/expenses/expenseFixtures'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)
const tripWithMembers = { ...trip, members }

async function mountList(expenses: Expense[], day = '2026-11-05') {
  get.mockResolvedValue({ expenses })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }],
  })
  const wrapper = mount(ExpenseList, {
    props: { trip: tripWithMembers, day },
    global: { plugins: [createAppI18n('en'), router] },
  })
  await flushPromises()
  return wrapper
}

const rowButtons = (wrapper: Awaited<ReturnType<typeof mountList>>) =>
  wrapper.findAll('li > button')

beforeEach(() => {
  get.mockReset()
})

describe('collapsed row', () => {
  it('renders category icon, title, payer, participant ratio, and amount', async () => {
    const wrapper = await mountList([expense({ a: 50_000, b: 50_000, c: 0 })])
    const row = rowButtons(wrapper)[0]
    expect(row?.text()).toContain('Noodles')
    expect(row?.text()).toContain('Alex paid · 2/3 people')
    expect(row?.text()).toContain('100,000')
    expect(row?.find('svg').exists()).toBe(true)
    expect(row?.attributes('aria-expanded')).toBe('false')
  })

  it('displays Group fund when paid_by is null', async () => {
    const wrapper = await mountList([expense({ a: 10, b: 10, c: 10 }, { paid_by: null })])
    expect(rowButtons(wrapper)[0]?.text()).toContain('Group fund paid · 3/3 people')
  })
})

describe('expanding row panels', () => {
  const two = [
    expense({ a: 50, b: 50 }, { id: 'e1', title: 'First' }),
    expense({ a: 50, b: 50 }, { id: 'e2', title: 'Second' }),
  ]

  it('opens one row at a time and collapses on a second click', async () => {
    const wrapper = await mountList(two)
    await rowButtons(wrapper)[0]?.trigger('click')
    expect(wrapper.findAll('[id^="expense-panel-"]')).toHaveLength(1)
    expect(rowButtons(wrapper)[0]?.attributes('aria-expanded')).toBe('true')
    expect(rowButtons(wrapper)[0]?.attributes('aria-controls')).toBe('expense-panel-e1')

    await rowButtons(wrapper)[1]?.trigger('click')
    expect(wrapper.findAll('[id^="expense-panel-"]').map((el) => el.attributes('id'))).toEqual([
      'expense-panel-e2',
    ])
    expect(rowButtons(wrapper)[0]?.attributes('aria-expanded')).toBe('false')

    await rowButtons(wrapper)[1]?.trigger('click')
    expect(wrapper.find('[id^="expense-panel-"]').exists()).toBe(false)
  })

  it('collapses any expanded row when day changes', async () => {
    const wrapper = await mountList(two)
    await rowButtons(wrapper)[0]?.trigger('click')
    await wrapper.setProps({ day: '2026-11-06' })
    await flushPromises()
    expect(wrapper.find('[id^="expense-panel-"]').exists()).toBe(false)
  })

  it('shows even per-person line and exempt members', async () => {
    const wrapper = await mountList([expense({ a: 50_000, b: 50_000, c: 0 })])
    await rowButtons(wrapper)[0]?.trigger('click')
    const panel = wrapper.get('[id^="expense-panel-"]').text()
    expect(panel).toContain('₫50,000 each · split equally')
    expect(panel).toContain('Exempt: Claire')
  })

  it('shows a min-max range for uneven splits', async () => {
    const wrapper = await mountList([
      expense({ a: 70_000, b: 30_000, c: 0 }, { split_mode: 'exact' }),
    ])
    await rowButtons(wrapper)[0]?.trigger('click')
    const panel = wrapper.get('[id^="expense-panel-"]').text()
    expect(panel).toContain('Uneven split · ₫30,000–₫70,000')
  })

  it('truncates exempt list after two names', async () => {
    const many = [
      ...members,
      { id: 'e', display_name: 'Dan', position: 4, removed: false },
      { id: 'f', display_name: 'Emma', position: 5, removed: false },
    ]
    get.mockResolvedValue({ expenses: [expense({ a: 100 })] })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }],
    })
    const wrapper = mount(ExpenseList, {
      props: { trip: { ...trip, members: many }, day: '2026-11-05' },
      global: { plugins: [createAppI18n('en'), router] },
    })
    await flushPromises()
    await rowButtons(wrapper)[0]?.trigger('click')
    expect(wrapper.get('[id^="expense-panel-"]').text()).toContain('Exempt: Ben, Claire and 2 more')
  })

  it('omits note and map link rows when absent', async () => {
    const wrapper = await mountList([expense({ a: 100 }, { split_mode: 'exact' })])
    await rowButtons(wrapper)[0]?.trigger('click')
    const panel = wrapper.get('[id^="expense-panel-"]')
    expect(panel.find('a[target="_blank"]').exists()).toBe(false)
    expect(panel.find('p').exists()).toBe(false)
    expect(panel.findAll('ul li')).toHaveLength(2)
  })

  it('renders literal note text without HTML parsing and encodes Google Maps place links', async () => {
    const wrapper = await mountList([
      expense({ a: 50, b: 50 }, { note: 'Line one\nLine <b>two</b>', place: 'Cafe A & B, Da Lat' }),
    ])
    await rowButtons(wrapper)[0]?.trigger('click')
    const note = wrapper.get('[id^="expense-panel-"] p')
    expect(note.text()).toBe('Line one\nLine <b>two</b>')
    expect(note.classes()).toContain('whitespace-pre-wrap')
    expect(note.find('b').exists()).toBe(false)
    const place = wrapper.get('a[target="_blank"]')
    expect(place.attributes('href')).toBe(
      'https://www.google.com/maps/search/?api=1&query=Cafe%20A%20%26%20B%2C%20Da%20Lat',
    )
    expect(place.attributes('rel')).toBe('noopener noreferrer')
    expect(place.text()).toBe('Cafe A & B, Da Lat')
  })

  it('links to detail and edit views and emits delete', async () => {
    const wrapper = await mountList([expense({ a: 50, b: 50 })])
    await rowButtons(wrapper)[0]?.trigger('click')
    const hrefs = wrapper.findAll('[id^="expense-panel-"] a').map((a) => a.attributes('href'))
    expect(hrefs).toEqual(['/trips/abc/expenses/e1', '/trips/abc/expenses/e1/edit'])
    expect(wrapper.find('a[aria-label="Edit expense"]').exists()).toBe(true)
    await wrapper.get('button[aria-label="Delete expense"]').trigger('click')
    expect(wrapper.emitted('delete')?.[0]).toEqual([expect.objectContaining({ id: 'e1' })])
  })
})

describe('loading and errors', () => {
  it('renders loading skeleton while pending', () => {
    get.mockReturnValue(new Promise(() => undefined))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }],
    })
    const wrapper = mount(ExpenseList, {
      props: { trip: tripWithMembers, day: '2026-11-05' },
      global: { plugins: [createAppI18n('en'), router] },
    })
    expect(wrapper.get('[aria-busy="true"]').text()).toBe('Loading…')
  })

  it('renders error alert and recovers on retry', async () => {
    get.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    const wrapper = await mountList([])
    expect(wrapper.get('[role="alert"]').text()).toContain('No connection')
    get.mockResolvedValueOnce({ expenses: [expense({ a: 1 })] })
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(rowButtons(wrapper)).toHaveLength(1)
  })
})
