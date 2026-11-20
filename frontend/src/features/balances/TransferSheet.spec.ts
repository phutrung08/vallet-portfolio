import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import QrCode from '@/components/QrCode.vue'
import type { VietQr } from '@/entities'
import { account, balances, serveBalances } from '@/features/balances/balanceFixtures'
import { mountBalances, unmountBalances } from '@/features/balances/balanceHarness'
import { ApiError, api } from '@/lib/api'
import { button, click, dialog, typeInto } from '@/lib/domTestHelpers'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
const writeText = vi.fn()

const qr: VietQr = {
  payload: '00020101021238540010A000000727',
  bank_bin: '970436',
  bank_short_name: 'Vietcombank',
  account_name: 'ALEX RIVERA',
  account_last4: '6789',
  amount: 70_000,
  message: 'Vallet Da Lat',
}
const mineLabel = '[aria-label="QR code: Ben pays Alex"]'
const othersLabel = '[aria-label="QR code: Ben pays Former guest"]'

/** Balances responses plus the VietQR endpoint controlled by the test case. */
function serve(vietqr: (path: string) => Promise<unknown>) {
  const balancesGet = serveBalances({}, balances, [], [account])
  get.mockImplementation((path: string) =>
    path.includes('/vietqr?') ? vietqr(path) : balancesGet(path),
  )
}

const refusal = (code: string) => () => Promise.reject(new ApiError(409, code, code))
const amountField = () => dialog()?.querySelector<HTMLInputElement>('input[inputmode="numeric"]')

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({})
  writeText.mockReset().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
  vi.setSystemTime(new Date('2026-11-06T12:00:00'))
})

afterEach(() => {
  vi.useRealTimers()
  unmountBalances()
})

describe('transfer sheet with a QR', () => {
  it('draws the payload and shows the account to check', async () => {
    serve(() => Promise.resolve(qr))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(get).toHaveBeenCalledWith('/trips/abc/vietqr?payee=1&amount=70000', {
      signal: expect.any(AbortSignal),
    })
    expect(dialog()?.querySelector('h2')?.textContent).toBe('Ben pays Alex')
    expect(amountField()?.value).toBe('70,000')
    expect(view.findComponent(QrCode).props()).toMatchObject({ value: qr.payload, size: 240 })
    const text = dialog()?.textContent ?? ''
    expect(text).toContain('Vietcombank')
    expect(text).toContain('6789')
    expect(text).toContain('ALEX RIVERA')
    expect(text).toContain('Vallet Da Lat')
  })

  it('copies the amount as plain digits', async () => {
    serve(() => Promise.resolve(qr))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    await click(button(dialog(), 'Copy amount'))
    expect(writeText).toHaveBeenCalledWith('70000')
    expect(button(dialog(), 'Copied')).toBeDefined()
  })

  it('records the payment, then refreshes the balances and closes', async () => {
    serve(() => Promise.resolve(qr))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    await click(button(dialog(), "I've paid"))
    const [path, body, options] = post.mock.calls[0] ?? []
    expect(path).toBe('/trips/abc/payments')
    expect(body).toEqual({ payer: '2', payee: '1', amount: 70_000, paid_on: '2026-11-06' })
    expect(options?.idempotencyKey).toMatch(/^[0-9a-f-]{36}$/)
    expect(get.mock.calls.filter(([url]) => url === '/trips/abc/balances')).toHaveLength(2)
    expect(dialog()).toBeNull()
  })

  it('reuses the idempotency key when the same payment is retried', async () => {
    serve(() => Promise.resolve(qr))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    post.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    await click(button(dialog(), "I've paid"))
    expect(dialog()?.textContent).toContain('No connection')
    await click(button(dialog(), "I've paid"))
    expect(post).toHaveBeenCalledTimes(2)
    expect(post.mock.calls[1]?.[2]?.idempotencyKey).toBe(post.mock.calls[0]?.[2]?.idempotencyKey)
    expect(dialog()).toBeNull()
  })

  it('records a partial amount with a new key and a QR for that amount', async () => {
    serve((path) => Promise.resolve({ ...qr, amount: Number(path.split('amount=')[1]) }))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    post.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    await click(button(dialog(), "I've paid"))
    await typeInto(amountField(), '20000')
    expect(get).not.toHaveBeenCalledWith('/trips/abc/vietqr?payee=1&amount=20000', {
      signal: expect.any(AbortSignal),
    })
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/trips/abc/vietqr?payee=1&amount=20000', {
      signal: expect.any(AbortSignal),
    })
    await click(button(dialog(), "I've paid"))
    expect(post.mock.calls[1]?.[1]).toMatchObject({ amount: 20_000 })
    expect(post.mock.calls[1]?.[2]?.idempotencyKey).not.toBe(post.mock.calls[0]?.[2]?.idempotencyKey)
  })

  it('refuses an empty or too large amount without calling the server', async () => {
    serve(() => Promise.resolve(qr))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    await typeInto(amountField(), '80000')
    expect(dialog()?.textContent).toContain('At most ₫70,000')
    expect(button(dialog(), "I've paid")?.disabled).toBe(true)
    await typeInto(amountField(), '')
    expect(dialog()?.textContent).toContain('Enter an amount')
    expect(button(dialog(), 'Copy amount')).toBeUndefined()
    expect(post).not.toHaveBeenCalled()
  })
})

describe('transfer sheet without a QR', () => {
  it('says the payee has no account and offers to add mine when I am the payee', async () => {
    serve(refusal('no_bank_account'))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(dialog()?.textContent).toContain('Alex has not added a bank account')
    await click(button(dialog(), 'Add my account'))
    expect(dialog()?.querySelector('h2')?.textContent).toBe('Receiving account')
  })

  it('does not offer to add an account for somebody else', async () => {
    serve(refusal('no_bank_account'))
    const view = await mountBalances()
    await click(view.get(othersLabel).element)
    expect(dialog()?.textContent).toContain('has not added a bank account')
    expect(button(dialog(), 'Add my account')).toBeUndefined()
  })

  it('explains that QR is for VND trips and still lets me record the payment', async () => {
    serve(refusal('currency_not_supported'))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(dialog()?.textContent).toContain('QR codes only work for trips in VND')
    await click(button(dialog(), "I've paid"))
    expect(post).toHaveBeenCalledTimes(1)
    expect(dialog()).toBeNull()
  })

  it('offers a retry for other failures', async () => {
    serve(refusal('network_error'))
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(dialog()?.textContent).toContain('No connection')
    await click(button(dialog(), 'Try again'))
    expect(get.mock.calls.filter(([url]) => url.includes('/vietqr?'))).toHaveLength(2)
  })
})

describe('transfer sheet account-change warning', () => {
  function serveChange(changedAt: string | null) {
    const balancesGet = serveBalances({}, balances, [], [{ ...account, bank_account_changed_at: changedAt }])
    get.mockImplementation((path: string) =>
      path.includes('/vietqr?') ? Promise.resolve(qr) : balancesGet(path),
    )
  }
  const note = () => dialog()?.querySelector('[role="note"]')

  it('warns above the QR when the payee changed the account within 7 days', async () => {
    serveChange('2026-11-05T21:40:00')
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(note()?.textContent).toContain('Alex changed their receiving account at 21:40 yesterday.')
    expect(note()?.textContent).toContain('Check with Alex before you pay if this looks wrong.')
    expect(note()?.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
    const qrImg = dialog()?.querySelector('svg[role="img"], [role="img"]')
    expect(qrImg).not.toBeNull()
    const nodes = [...(dialog()?.querySelectorAll('[role="note"], [role="img"]') ?? [])]
    expect(nodes[0]).toBe(note())
  })

  it('names today and still warns at the edge of the window', async () => {
    serveChange('2026-11-06T09:12:00')
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(note()?.textContent).toContain('at 09:12 today.')
  })

  it('stays quiet when the change is older than 7 days', async () => {
    serveChange('2026-10-29T11:59:00')
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(dialog()?.textContent).toContain('Vietcombank')
    expect(note()).toBeNull()
  })

  it('stays quiet when the account never changed', async () => {
    serveChange(null)
    const view = await mountBalances()
    await click(view.get(mineLabel).element)
    expect(note()).toBeNull()
  })
})
