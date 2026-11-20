import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { TripDetail } from '@/entities'
import ExpenseFormView from '@/features/expenses/ExpenseFormView.vue'
import { field, fillValid, mountExpenseForm } from '@/features/expenses/expenseFormHarness'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { dialog } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
let wrapper: VueWrapper | undefined

async function mountForm(overrides: Partial<TripDetail> = {}, today = '2026-11-06') {
  get.mockResolvedValue({ ...trip, ...overrides })
  const mounted = await mountExpenseForm('/trips/abc/expenses/new', today)
  wrapper = mounted.wrapper
  return mounted
}

const save = (form: VueWrapper) => form.get('button[type="submit"]')
const sheetButtons = () => [...(dialog()?.querySelectorAll<HTMLButtonElement>('li button') ?? [])]

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({ id: 'e1', spent_on: '2026-11-06' })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('ExpenseFormView loading', () => {
  it('fetches trip with AbortSignal and populates form defaults', async () => {
    const { wrapper } = await mountForm()
    expect(get).toHaveBeenCalledWith('/trips/abc', { signal: expect.any(AbortSignal) })
    expect(wrapper.get('h1').text()).toBe('Add expense')
    expect(field(wrapper, 'Date').element).toHaveProperty('value', '2026-11-06')
    expect(wrapper.get('input[type="radio"]:checked').element).toHaveProperty('value', 'food')
    expect(wrapper.text()).toContain('Alex (you)')
    expect(wrapper.text()).toContain('Split between 2 people')
    expect(field(wrapper, 'Amount').attributes('inputmode')).toBe('numeric')
  })

  it('defaults date to trip start when today is outside trip range', async () => {
    const { wrapper } = await mountForm({}, '2026-12-01')
    expect(field(wrapper, 'Date').element).toHaveProperty('value', '2026-11-05')
  })

  it('renders not-found message without retry button on 404', async () => {
    get.mockRejectedValue(new ApiError(404, 'not_found', 'Not Found'))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/trips/:tripId', component: { template: '<div />' } },
        { path: '/trips/:tripId/expenses/new', component: ExpenseFormView },
      ],
    })
    await router.push('/trips/abc/expenses/new')
    wrapper = mount(ExpenseFormView, { global: { plugins: [createAppI18n('en'), router] } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe("We couldn't find this trip.")
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it.each([
    [{ locked: true }, 'This trip is locked, so it is view-only.'],
    [{ closed: true }, "This trip is settled, so it can't be changed."],
  ])('renders read-only notice for %j', async (overrides, notice) => {
    const { wrapper } = await mountForm(overrides)
    expect(wrapper.get('[role="alert"]').text()).toBe(notice)
    expect(wrapper.find('form').exists()).toBe(false)
  })
})

describe('amount input formatting', () => {
  it('inserts thousands commas for VND', async () => {
    const { wrapper } = await mountForm()
    const amount = field(wrapper, 'Amount')
    await amount.setValue('395000')
    expect(amount.element).toHaveProperty('value', '395,000')
  })

  it('permits up to two decimals for USD', async () => {
    const { wrapper } = await mountForm({ currency: 'USD' })
    const amount = field(wrapper, 'Amount')
    expect(amount.attributes('inputmode')).toBe('decimal')
    await amount.setValue('12.345')
    expect(amount.element).toHaveProperty('value', '12.34')
  })
})

describe('payer picker dialog', () => {
  it('lists active members without shared fund when disabled', async () => {
    const { wrapper } = await mountForm()
    await wrapper.get('button[aria-haspopup="dialog"]').trigger('click')
    expect(sheetButtons().map((button) => button.textContent?.trim())).toEqual([
      'AAlex (you)',
      'BBen',
    ])
  })

  it('includes shared fund when enabled and submits null paid_by', async () => {
    const { wrapper } = await mountForm({ fund_holder_id: '2' })
    await wrapper.get('button[aria-haspopup="dialog"]').trigger('click')
    const fund = sheetButtons().find((button) => button.textContent?.includes('Group fund'))
    fund?.click()
    await flushPromises()
    expect(dialog()).toBeNull()
    expect(wrapper.get('button[aria-haspopup="dialog"]').text()).toContain('Group fund')
    await fillValid(wrapper)
    await wrapper.get('form').trigger('submit')
    expect(post.mock.calls[0]?.[1]).toMatchObject({ paid_by: null })
  })

  it('switches payer to another active member', async () => {
    const { wrapper } = await mountForm()
    await wrapper.get('button[aria-haspopup="dialog"]').trigger('click')
    sheetButtons()[1]?.click()
    await flushPromises()
    await fillValid(wrapper)
    await wrapper.get('form').trigger('submit')
    expect(post.mock.calls[0]?.[1]).toMatchObject({ paid_by: '2' })
  })
})

describe('submitting expenses', () => {
  it('validates locally prior to sending network requests', async () => {
    const { wrapper } = await mountForm()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.findAll('[role="alert"]').map((alert) => alert.text())).toEqual([
      'Enter an amount',
      'Enter what it was for',
    ])
    expect(post).not.toHaveBeenCalled()
  })

  it('posts request payload with Idempotency-Key and opens trip day view', async () => {
    const { wrapper, router } = await mountForm()
    await fillValid(wrapper)
    await wrapper.get('input[value="transport"]').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const [path, body, options] = post.mock.calls[0] ?? []
    expect(path).toBe('/trips/abc/expenses')
    expect(body).toEqual({
      title: 'Noodles',
      amount: 395_000,
      category: 'transport',
      spent_on: '2026-11-06',
      paid_by: '1',
      split: { mode: 'equal', participants: ['1', '2'] },
      note: null,
      place: null,
    })
    expect(options?.idempotencyKey).toMatch(/^[0-9a-f-]{36}$/)
    await vi.waitFor(() =>
      expect(router.currentRoute.value.fullPath).toBe('/trips/abc?day=2026-11-06'),
    )
  })

  it('disables submit button while saving and prevents double POST', async () => {
    let finish: (value: unknown) => void = () => undefined
    post.mockImplementationOnce(() => new Promise((resolve) => (finish = resolve)))
    const { wrapper } = await mountForm()
    await fillValid(wrapper)
    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')
    expect(save(wrapper).attributes('disabled')).toBeDefined()
    expect(save(wrapper).text()).toBe('Saving…')
    expect(post).toHaveBeenCalledTimes(1)
    finish({ id: 'e1', spent_on: '2026-11-06' })
    await flushPromises()
  })

  it('reuses idempotency key on retry and rotates key on new form instances', async () => {
    post.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    const first = await mountForm()
    await fillValid(first.wrapper)
    await first.wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(first.wrapper.text()).toContain('No connection')
    await first.wrapper.get('form').trigger('submit')
    await flushPromises()
    const [firstKey, retryKey] = post.mock.calls.map((call) => call[2]?.idempotencyKey)
    expect(retryKey).toBe(firstKey)
    first.wrapper.unmount()

    const second = await mountForm()
    await fillValid(second.wrapper)
    await second.wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(post.mock.calls[2]?.[2]?.idempotencyKey).not.toBe(firstKey)
  })
})

describe('server errors', () => {
  async function submitWith(error: ApiError) {
    post.mockRejectedValueOnce(error)
    const { wrapper } = await mountForm()
    await fillValid(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    return wrapper
  }

  it.each([
    ['trip_locked', 'This trip is locked, so it is view-only.'],
    ['trip_closed', "This trip is settled, so it can't be changed."],
    ['member_not_active', 'Someone on this action is no longer active in the trip. Reload and try again.'],
    ['no_fund', 'This trip has no shared fund.'],
    ['trip_limit_reached', 'This trip has reached the maximum number of records.'],
    ['internal_error', 'Something went wrong. Please try again.'],
  ])('maps error code %s cleanly', async (code, text) => {
    const wrapper = await submitWith(new ApiError(409, code, 'x'))
    expect(wrapper.get('[role="alert"]').text()).toBe(text)
  })

  it('renders invalid_split shortfall or excess delta', async () => {
    const missing = await submitWith(new ApiError(422, 'invalid_split', 'x', undefined, [], 8_000))
    expect(missing.get('[role="alert"]').text()).toBe('₫8,000 short')
    missing.unmount()
    const excess = await submitWith(new ApiError(422, 'invalid_split', 'x', undefined, [], -2_000))
    expect(excess.get('[role="alert"]').text()).toBe('₫2,000 over')
  })

  it('marks invalid server fields with aria-invalid', async () => {
    const wrapper = await submitWith(
      new ApiError(422, 'validation_error', 'x', undefined, ['body.title']),
    )
    expect(field(wrapper, 'What for').attributes('aria-invalid')).toBe('true')
    expect(wrapper.get('[role="alert"]').text()).toBe('This is not valid')
  })
})
