import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ExpenseDetailPane from '@/features/expenses/ExpenseDetailPane.vue'
import { expense, members } from '@/features/expenses/expenseFixtures'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)
const sampleBill = expense({ a: 50_000, b: 50_000 }, { note: 'Extra herbs', place: 'Da Lat Market' })

async function mountPane(props: { trip?: typeof trip; expenseId?: string } = {}, url = '/') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
  await router.push(url)
  const wrapper = mount(ExpenseDetailPane, {
    props: { trip: { ...trip, members }, expenseId: 'e1', today: '2026-11-06', ...props },
    global: { plugins: [createAppI18n('en'), router] },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  get.mockReset()
  get.mockResolvedValue(sampleBill)
})

describe('ExpenseDetailPane', () => {
  it('fetches expense with AbortSignal and renders amount, shares, note, and place', async () => {
    const wrapper = await mountPane()
    expect(get).toHaveBeenCalledWith('/trips/abc/expenses/e1', { signal: expect.any(AbortSignal) })
    expect(wrapper.get('h2').text()).toBe('Noodles')
    const text = wrapper.text()
    expect(text).toContain('100,000')
    expect(text).toContain('Food')
    expect(text).toContain('Alex')
    expect(text).toContain('Ben')
    expect(text).toContain('Extra herbs')
    expect(wrapper.get('a[href*="maps"]').text()).toBe('Da Lat Market')
  })

  it('offers Edit and Delete actions and emits delete request to parent', async () => {
    const wrapper = await mountPane()
    const labels = wrapper.findAll('button').map((button) => button.text())
    expect(labels).toEqual(['Edit expense', 'Delete expense'])
    await wrapper.findAll('button')[1]?.trigger('click')
    expect(wrapper.emitted('delete')?.[0]).toEqual([sampleBill])
  })

  it('opens edit form automatically for ?edit=yes and removes edit param from URL', async () => {
    const wrapper = await mountPane({}, '/?expense=e1&edit=yes')
    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.vm.$router.currentRoute.value.query).toEqual({ expense: 'e1' })
  })

  it('hides mutation actions on locked trip', async () => {
    const wrapper = await mountPane({ trip: { ...trip, members, locked: true } })
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.text()).toContain('This trip is locked')
  })

  it('reloads details when expenseId prop changes', async () => {
    const wrapper = await mountPane()
    await wrapper.setProps({ expenseId: 'e2' })
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('/trips/abc/expenses/e2', { signal: expect.any(AbortSignal) })
  })

  it('renders not-found message without retry button on 404', async () => {
    get.mockRejectedValue(new ApiError(404, 'not_found', 'Not Found'))
    const wrapper = await mountPane()
    expect(wrapper.get('[role="alert"]').text()).toContain("We couldn't find this expense")
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
})
