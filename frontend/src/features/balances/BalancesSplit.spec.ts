import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { Balances, VietQr } from '@/entities'
import { account, balances, payment, serveBalances } from '@/features/balances/balanceFixtures'
import { balancesRouter, mountBalances, unmountBalances } from '@/features/balances/balanceHarness'
import { api } from '@/lib/api'
import { click, dialog } from '@/lib/domTestHelpers'
import { mockSplit } from '@/lib/splitTestHelpers'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)

const qr: VietQr = {
  payload: '00020101021238540010A000000727',
  bank_bin: '970436',
  bank_short_name: 'Vietcombank',
  account_name: 'ALEX RIVERA',
  account_last4: '6789',
  amount: 70_000,
  message: 'Vallet Da Lat',
}
const mine = '[aria-label="QR code: Ben pays Alex"]'
const others = '[aria-label="QR code: Ben pays Former guest"]'

function serve(out: Balances = balances, tripOverrides = {}, accounts = [account]) {
  const answer = serveBalances(tripOverrides, out, [payment], accounts)
  get.mockImplementation((path: string) => (path.includes('/vietqr?') ? Promise.resolve(qr) : answer(path)))
}

const transferParam = () => balancesRouter().currentRoute.value.query.transfer

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({})
  mockSplit(true)
})

afterEach(unmountBalances)

describe('balances on a split layout', () => {
  it('opens the first transfer I am part of in the right pane', async () => {
    serve()
    const view = await mountBalances()
    expect(transferParam()).toBe('2.1')
    expect(view.get(mine).attributes('aria-current')).toBe('true')
    expect(view.get(others).attributes('aria-current')).toBeUndefined()
    const pane = view.get('.split-detail')
    expect(pane.text()).toContain('Ben pays Alex')
    expect(pane.text()).toContain('Vietcombank')
    expect(pane.text()).toContain("I've paid")
    expect(dialog()).toBeNull()
  })

  it('falls back to the first transfer when I am in none', async () => {
    serve({ ...balances, transfers: [{ payer: '3', payee: '2', amount: 5_000 }] })
    await mountBalances()
    expect(transferParam()).toBe('3.2')
  })

  it('shows another transfer on a tap, as a new history entry', async () => {
    serve()
    const view = await mountBalances()
    await click(view.get(others).element)
    expect(transferParam()).toBe('2.3')
    expect(view.get('.split-detail').text()).toContain('Ben pays Former guest')
    expect(view.get(others).attributes('aria-current')).toBe('true')
    await balancesRouter().back()
    await flushPromises()
    expect(transferParam()).toBe('2.1')
  })

  it('records the payment from the pane and moves on once the transfer is settled', async () => {
    serve()
    const view = await mountBalances()
    serve({ ...balances, transfers: [{ payer: '2', payee: '3', amount: 30_000 }] })
    await click(
      [...view.get('.split-detail').element.querySelectorAll('button')].find((item) =>
        item.textContent?.includes("I've paid"),
      ),
    )
    expect(post).toHaveBeenCalledOnce()
    expect(transferParam()).toBe('2.3')
  })

  it('keeps the account-changed warning beside the QR', async () => {
    const recent = new Date(Date.now() - 86_400_000).toISOString()
    serve(balances, {}, [{ ...account, bank_account_changed_at: recent }])
    const view = await mountBalances()
    expect(view.get('.split-detail [role="note"]').text()).toContain('Alex')
  })

  it('says everything is settled, with the summary link, when nothing is owed', async () => {
    serve({ ...balances, transfers: [] })
    const view = await mountBalances()
    const pane = view.get('.split-detail')
    expect(pane.text()).toContain('Everyone is square')
    expect(pane.find('a[href="/trips/abc/summary"]').exists()).toBe(true)
    expect(transferParam()).toBeUndefined()
  })

  it('does not pick or open a QR on a locked trip', async () => {
    serve(balances, { locked: true })
    const view = await mountBalances()
    expect(transferParam()).toBeUndefined()
    expect(view.find(mine).exists()).toBe(false)
    expect(view.get('.split-detail').text()).toContain('view-only')
  })
})

describe('balances below the split breakpoint', () => {
  it('keeps the sheet and leaves the URL alone', async () => {
    mockSplit(false)
    serve()
    const view = await mountBalances()
    expect(transferParam()).toBeUndefined()
    await click(view.get(mine).element)
    expect(dialog()).not.toBeNull()
    expect(transferParam()).toBeUndefined()
    expect(view.get(mine).attributes('aria-current')).toBeUndefined()
  })
})
