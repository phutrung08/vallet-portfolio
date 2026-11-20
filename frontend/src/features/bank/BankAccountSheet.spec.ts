import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { ref } from 'vue'
import type { Bank, BankAccount } from '@/entities'
import BankAccountSheet from '@/features/bank/BankAccountSheet.vue'
import { ApiError, api } from '@/lib/api'
import { button, click, dialog, submitSheet, typeInto } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const put = vi.mocked(api.put)
const del = vi.mocked(api.delete)

const banks: Bank[] = [
  { bin: '970436', code: 'VCB', short_name: 'Vietcombank' },
  { bin: '970415', code: 'ICB', short_name: 'VietinBank' },
  { bin: '971025', code: 'momo', short_name: 'MoMo' },
]

const savedAccount: BankAccount = {
  member_id: '1',
  bank_bin: '970436',
  bank_short_name: 'Vietcombank',
  account_last4: '6789',
  account_name: 'ALEX RIVERA',
  updated_at: '2026-11-05T10:00:00Z',
  bank_account_changed_at: null,
}

let wrapper: VueWrapper | undefined

async function mountSheet(current: BankAccount | null = null, changed = vi.fn(() => Promise.resolve())) {
  const open = ref(true)
  wrapper = mount(
    {
      components: { BankAccountSheet },
      setup: () => ({ open, current, changed }),
      template:
        '<BankAccountSheet :open="open" trip-id="abc" :current="current" :changed="changed" @close="open = false" />',
    },
    { attachTo: document.body, global: { plugins: [createAppI18n('en')] } },
  )
  await flushPromises()
  return { wrapper, changed, open }
}

const field = (index: number) => dialog()?.querySelectorAll('input')[index]
const search = () => field(0)
const number = () => field(1)
const holder = () => field(2)
const shownBanks = () =>
  [...(dialog()?.querySelectorAll('[aria-pressed]') ?? [])].map((item) => item.textContent ?? '')

beforeEach(() => {
  get.mockReset().mockResolvedValue({ banks })
  put.mockReset().mockResolvedValue(savedAccount)
  del.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('BankAccountSheet', () => {
  it('loads banks with AbortSignal and supports retry when loading fails', async () => {
    get.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    await mountSheet()
    expect(get).toHaveBeenCalledWith('/banks', { signal: expect.any(AbortSignal) })
    expect(dialog()?.textContent).toContain('No connection')

    get.mockResolvedValueOnce({ banks })
    await click(button(dialog(), 'Try again'))
    expect(shownBanks()).toHaveLength(3)
  })

  it('filters banks by short name or code, ignoring case and accents', async () => {
    await mountSheet()
    expect(shownBanks()).toHaveLength(3)
    await typeInto(search(), 'VCB')
    expect(shownBanks()).toHaveLength(1)
    expect(shownBanks()[0]).toContain('Vietcombank')
    await typeInto(search(), 'Việt')
    expect(shownBanks()).toHaveLength(2)
    await typeInto(search(), 'viet')
    expect(shownBanks()).toHaveLength(2)
    await typeInto(search(), 'zzz')
    expect(dialog()?.textContent).toContain('No bank found')
  })

  it('normalises account number to digits and previews uppercase holder name', async () => {
    await mountSheet()
    await typeInto(number(), '0123 456-789x')
    expect(number()?.value).toBe('0123456789')
    await typeInto(holder(), 'nguyễn văn đức')
    expect(holder()?.value).toBe('NGUYEN VAN DUC')
    expect(dialog()?.textContent).toContain('Will be printed as: NGUYEN VAN DUC')
  })

  it('validates bank, account number, and holder name prior to submission', async () => {
    await mountSheet()
    await typeInto(number(), '123')
    await submitSheet()
    const text = dialog()?.textContent ?? ''
    expect(text).toContain('Choose a bank')
    expect(text).toContain('The account number has 6 to 19 digits')
    expect(text).toContain('Letters and spaces only, at most 50 characters')
    expect(put).not.toHaveBeenCalled()
  })

  it('submits PUT payload, refreshes via changed hook, and closes dialog', async () => {
    const { changed } = await mountSheet()
    await click(dialog()?.querySelectorAll('[aria-pressed]')[0])
    await typeInto(number(), '0123456789')
    await typeInto(holder(), 'Alex  Rivera ')
    await submitSheet()
    expect(put).toHaveBeenCalledWith('/trips/abc/members/me/bank-account', {
      bank_bin: '970436',
      account_number: '0123456789',
      account_name: 'ALEX RIVERA',
    })
    expect(changed).toHaveBeenCalledTimes(1)
    expect(dialog()).toBeNull()
  })

  it('surfaces API submit errors without closing the form sheet', async () => {
    put.mockRejectedValueOnce(new ApiError(409, 'trip_locked', 'Locked'))
    await mountSheet()
    await click(dialog()?.querySelectorAll('[aria-pressed]')[0])
    await typeInto(number(), '0123456789')
    await typeInto(holder(), 'Alex Rivera')
    await submitSheet()
    expect(dialog()?.textContent).toContain('This trip is locked, so it is view-only.')
  })

  it('prefills masked bank summary and holder name when editing existing account', async () => {
    await mountSheet(savedAccount)
    expect(dialog()?.textContent).toContain('In use: Vietcombank •••• 6789')
    expect(number()?.value).toBe('')
    expect(holder()?.value).toBe('ALEX RIVERA')
    expect(dialog()?.querySelector('[aria-pressed="true"]')?.textContent).toContain('Vietcombank')
  })

  it('asks confirmation in stacked modal before removing saved bank account', async () => {
    const { changed } = await mountSheet(savedAccount)
    await click(button(dialog(), 'Remove account'))
    expect(dialog()?.textContent).toContain('Remove your receiving account?')
    expect(del).not.toHaveBeenCalled()

    await click(button(dialog(), 'Remove'))
    expect(del).toHaveBeenCalledWith('/trips/abc/members/me/bank-account')
    expect(changed).toHaveBeenCalledTimes(1)
    expect(dialog()).toBeNull()
  })
})
