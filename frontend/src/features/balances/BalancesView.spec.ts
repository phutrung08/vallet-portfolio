import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { balances, payment, serveBalances, standing } from '@/features/balances/balanceFixtures'
import { mountBalances, unmountBalances } from '@/features/balances/balanceHarness'
import { api } from '@/lib/api'
import { button, click, dialog } from '@/lib/domTestHelpers'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
const del = vi.mocked(api.delete)

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({})
  del.mockReset().mockResolvedValue(undefined)
})

afterEach(unmountBalances)

describe('BalancesView header and me card', () => {
  it('shows the title, trip name and the two tabs', async () => {
    get.mockImplementation(serveBalances())
    const view = await mountBalances()
    expect(view.get('h1').text()).toBe('Balances')
    expect(view.text()).toContain('Da Lat')
    const tabs = view.findAll('[aria-pressed]').map((tab) => tab.text())
    expect(tabs).toEqual(['Who pays whom', 'Per person'])
    expect(view.get('a[href="/trips/abc/summary"]').text()).toBe('Trip summary')
  })

  it('tells me what I get back, with what I fronted against my share', async () => {
    get.mockImplementation(serveBalances())
    const view = await mountBalances()
    expect(view.text()).toContain('You get back')
    expect(view.text()).toContain('+₫100,000')
    expect(view.text()).toContain('Fronted ₫500,000 · your share ₫400,000')
  })

  it('tells me what I owe', async () => {
    get.mockImplementation(
      serveBalances({}, { ...balances, members: [standing('1', { share: 50_000, net: -50_000 })] }),
    )
    const view = await mountBalances()
    expect(view.text()).toContain('You owe')
    expect(view.text()).toContain('₫50,000')
    expect(view.text()).not.toContain('-₫50,000')
    expect(view.find('.bg-yellow-soft').exists()).toBe(true)
  })

  it('tells me when I am done', async () => {
    get.mockImplementation(serveBalances({}, { ...balances, members: [standing('1')] }))
    const view = await mountBalances()
    expect(view.text()).toContain("You're all square")
  })
})

describe('BalancesView per-person tab', () => {
  it('switches to the per-person list and back', async () => {
    get.mockImplementation(serveBalances())
    const view = await mountBalances()
    await click(button(view.element, 'Per person'))
    expect(view.text()).toContain('Difference')
    expect(view.text()).not.toContain('You get back')
    await click(button(view.element, 'Who pays whom'))
    expect(view.text()).toContain('You get back')
  })
})

describe('BalancesView transfers', () => {
  it('lists my transfers first and counts them', async () => {
    get.mockImplementation(serveBalances())
    const view = await mountBalances()
    expect(view.text()).toContain('2 transfers')
    const rows = view.findAll('section')[0]?.findAll('li').map((row) => row.text()) ?? []
    expect(rows[0]).toContain('Ben')
    expect(rows[0]).toContain('Alex')
    expect(rows[0]).toContain('₫70,000')
    expect(rows[1]).toContain('₫30,000')
  })

  it('flags a removed member', async () => {
    get.mockImplementation(serveBalances())
    const view = await mountBalances()
    const second = view.findAll('section')[0]?.findAll('li')[1]
    expect(second?.text()).toContain('Former guest')
    expect(second?.text()).toContain('left')
  })

  it('celebrates when nobody has to pay', async () => {
    get.mockImplementation(serveBalances({}, { ...balances, transfers: [] }))
    const view = await mountBalances()
    expect(view.text()).toContain('Everyone is square')
    expect(view.text()).not.toContain('transfers')
  })
})

describe('BalancesView payments', () => {
  it('lists recorded payments, newest first, and deletes one after confirming', async () => {
    const older = { ...payment, id: 'p0', amount: 10_000, paid_on: '2026-11-06' }
    get.mockImplementation(serveBalances({}, balances, [older, payment]))
    const view = await mountBalances()
    const rows = view.findAll('section')[1]?.findAll('li') ?? []
    expect(rows[0]?.text()).toContain('₫20,000')
    expect(rows[1]?.text()).toContain('₫10,000')
    await click(view.get('[aria-label="Delete the transfer from Ben to Alex"]').element)
    expect(del).not.toHaveBeenCalled()
    await click(button(dialog(), 'Delete'))
    expect(del).toHaveBeenCalledWith('/trips/abc/payments/p1')
    expect(dialog()).toBeNull()
  })

  it('shows no history section without payments', async () => {
    get.mockImplementation(serveBalances())
    const view = await mountBalances()
    expect(view.text()).not.toContain('Paid')
  })
})

describe('BalancesView closing', () => {
  it('closes an open trip after explaining what that means', async () => {
    get.mockImplementation(serveBalances())
    const view = await mountBalances()
    await click(button(view.element, 'Close the trip'))
    expect(dialog()?.textContent).toContain('Transfers can still be recorded')
    await click(button(dialog(), 'Close'))
    expect(post).toHaveBeenCalledWith('/trips/abc/close')
    expect(dialog()).toBeNull()
  })

  it('reopens a closed trip and keeps payments available', async () => {
    get.mockImplementation(serveBalances({ closed: true }, balances, [payment]))
    const view = await mountBalances()
    expect(view.text()).toContain('Settled')
    expect(view.find('[aria-label^="Delete the transfer"]').exists()).toBe(true)
    await click(button(view.element, 'Reopen the trip'))
    await click(button(dialog(), 'Reopen'))
    expect(post).toHaveBeenCalledWith('/trips/abc/reopen')
  })

  it('hides every write and says why when the trip is locked', async () => {
    get.mockImplementation(serveBalances({ locked: true }, balances, [payment]))
    const view = await mountBalances()
    expect(view.text()).toContain('This trip is locked')
    expect(button(view.element, 'Close the trip')).toBeUndefined()
    expect(view.find('[aria-label^="Delete the transfer"]').exists()).toBe(false)
    expect(view.find('[aria-label^="QR code"]').exists()).toBe(false)
    expect(view.text()).not.toContain('Your receiving account')
  })
})
