import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { FundDetail, TripDetail } from '@/entities'
import FundView from '@/features/fund/FundView.vue'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { button, click, dialog, submitSheet, typeInto } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
const put = vi.mocked(api.put)
const del = vi.mocked(api.delete)
const stub = { template: '<div />' }
let wrapper: VueWrapper | undefined

const fund: FundDetail = {
  holder_id: '1',
  contributed: 500_000,
  spent: 120_000,
  remaining: 380_000,
  members: [{ member_id: '1', contributed: 500_000 }],
  contributions: [
    {
      id: 'c1',
      member_id: '1',
      amount: 300_000,
      contributed_on: '2026-11-04',
      created_by: '1',
      created_at: '2026-11-04T09:00:00Z',
    },
    {
      id: 'c2',
      member_id: '1',
      amount: 200_000,
      contributed_on: '2026-11-05',
      created_by: '1',
      created_at: '2026-11-05T09:00:00Z',
    },
  ],
}
const emptyFund: FundDetail = { ...fund, contributed: 0, spent: 0, remaining: 0, members: [], contributions: [] }

function serve(tripOverrides: Partial<TripDetail> = {}, fundOut: FundDetail | null = fund) {
  get.mockImplementation((path: string) => {
    if (path === '/trips/abc') {
      return Promise.resolve({ ...trip, fund_holder_id: fundOut ? '1' : null, ...tripOverrides })
    }
    if (path === '/trips/abc/fund' && fundOut) return Promise.resolve(fundOut)
    return Promise.reject(new Error(`unexpected GET ${path}`))
  })
}

async function mountFund() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/trips/:tripId', component: stub },
      { path: '/trips/:tripId/fund', component: FundView },
    ],
  })
  await router.push('/trips/abc/fund')
  await router.isReady()
  wrapper = mount(FundView, {
    props: { now: () => new Date('2026-11-06T12:00:00') },
    attachTo: document.body,
    global: { plugins: [createAppI18n('en'), router] },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({})
  put.mockReset().mockResolvedValue({})
  del.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('FundView with active fund', () => {
  it('displays remaining fund balance, holder, member totals, and newest-first history', async () => {
    serve()
    const view = await mountFund()
    expect(get).toHaveBeenCalledWith('/trips/abc/fund', { signal: expect.any(AbortSignal) })
    expect(view.get('h1').text()).toBe('Shared fund')
    expect(view.text()).toContain('Left in the fund')
    expect(view.text()).toContain('380,000')
    expect(view.text()).toContain('Holder: Alex')
    const members = view.findAll('section')[0]?.findAll('li') ?? []
    expect(members).toHaveLength(2)
    expect(members[0]?.text()).toContain('500,000')
    expect(members[0]?.text()).not.toContain('Not paid')
    expect(members[1]?.text()).toContain('Ben')
    expect(members[1]?.text()).toContain('Not paid')
    expect(view.text()).not.toContain('Former guest')
    const history = view.findAll('section')[1]?.findAll('li').map((row) => row.text()) ?? []
    expect(history[0]).toContain('200,000')
    expect(history[1]).toContain('300,000')
    expect(view.text()).toContain('If the fund runs short, anyone can pay from their own pocket')
  })

  it('posts contribution with idempotency key and reuses the key on retry', async () => {
    serve()
    const view = await mountFund()
    post.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    await click(button(view.element, 'Record a contribution'))
    const sheet = dialog()
    expect(sheet?.querySelector('input[type="date"]')).toHaveProperty('value', '2026-11-06')
    expect(sheet?.querySelector('[aria-pressed="true"]')?.textContent).toContain('Alex')
    await typeInto(sheet?.querySelector('input[inputmode="numeric"]'), '150000')
    await submitSheet()
    expect(dialog()?.textContent).toContain('No connection')
    await submitSheet()
    expect(post).toHaveBeenCalledTimes(2)
    const [path, body, options] = post.mock.calls[0] ?? []
    expect(path).toBe('/trips/abc/fund/contributions')
    expect(body).toEqual({ member_id: '1', amount: 150_000, contributed_on: '2026-11-06' })
    const key = options?.idempotencyKey
    expect(key).toMatch(/^[0-9a-f-]{36}$/)
    expect(post.mock.calls[1]?.[2]?.idempotencyKey).toBe(key)
    expect(dialog()).toBeNull()
  })

  it('validates non-empty contribution amount before API submission', async () => {
    serve()
    const view = await mountFund()
    await click(button(view.element, 'Record a contribution'))
    await submitSheet()
    expect(dialog()?.textContent).toContain('Enter an amount')
    expect(post).not.toHaveBeenCalled()
  })

  it('confirms deletion in native dialog before removing contribution', async () => {
    serve()
    const view = await mountFund()
    await click(view.get('[aria-label="Delete Alex\'s contribution"]').element)
    expect(del).not.toHaveBeenCalled()
    await click(button(dialog(), 'Delete'))
    expect(del).toHaveBeenCalledWith('/trips/abc/fund/contributions/c2')
    expect(dialog()).toBeNull()
  })

  it('transfers fund holder to another active member', async () => {
    serve()
    const view = await mountFund()
    await click(button(view.element, 'Change holder'))
    const save = button(dialog(), 'Save')
    expect(save?.disabled).toBe(true)
    const ben = [...(dialog()?.querySelectorAll('li button') ?? [])].find((item) => item.textContent?.includes('Ben'))
    await click(ben)
    await click(save)
    expect(put).toHaveBeenCalledWith('/trips/abc/fund', { holder_id: '2' })
    expect(dialog()).toBeNull()
  })

  it('shows turn-off option only when fund has no contributions or expenses', async () => {
    serve()
    expect(button((await mountFund()).element, 'Turn off shared fund')).toBeUndefined()
    wrapper?.unmount()
    serve({}, emptyFund)
    expect(button((await mountFund()).element, 'Turn off shared fund')).toBeDefined()
  })

  it('turns off shared fund and surfaces mapped error on fund_in_use', async () => {
    serve({}, emptyFund)
    const view = await mountFund()
    put.mockRejectedValueOnce(new ApiError(409, 'fund_in_use', 'in use'))
    await click(button(view.element, 'Turn off shared fund'))
    await click(button(dialog(), 'Turn off'))
    expect(dialog()?.textContent).toContain('The fund has contributions or fund-paid expenses')
    await click(button(dialog(), 'Turn off'))
    expect(put).toHaveBeenLastCalledWith('/trips/abc/fund', { holder_id: null })
    expect(dialog()).toBeNull()
  })

  it.each([
    ['locked', { locked: true }, 'This trip is locked'],
    ['closed', { closed: true }, 'This trip is settled'],
  ])('hides mutating actions when trip is %s', async (_name, overrides, reason) => {
    serve(overrides)
    const view = await mountFund()
    expect(view.text()).toContain(reason)
    expect(button(view.element, 'Record a contribution')).toBeUndefined()
    expect(button(view.element, 'Change holder')).toBeUndefined()
    expect(view.find('[aria-label^="Delete "]').exists()).toBe(false)
  })
})

describe('FundView when disabled', () => {
  it('renders empty state and enables fund with current member as holder', async () => {
    serve({}, null)
    const view = await mountFund()
    expect(view.text()).toContain('This trip has no shared fund')
    expect(button(view.element, 'Record a contribution')).toBeUndefined()
    await click(button(view.element, 'Turn on shared fund'))
    expect(put).toHaveBeenCalledWith('/trips/abc/fund', { holder_id: '1' })
  })

  it('hides Turn on button when trip is locked', async () => {
    serve({ locked: true }, null)
    const view = await mountFund()
    expect(button(view.element, 'Turn on shared fund')).toBeUndefined()
    expect(view.text()).toContain('This trip is locked')
  })
})
