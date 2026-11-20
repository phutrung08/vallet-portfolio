import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import type { TripMember } from '@/entities'
import { field, fillValid, mountExpenseForm } from '@/features/expenses/expenseFormHarness'
import { trip } from '@/features/trips/tripFixtures'
import { api } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
// Deliberately unsorted input list to verify position ordering.
const members: TripMember[] = [
  { id: '4', display_name: 'Clara', position: 3, removed: false },
  { id: '1', display_name: 'Alex', position: 0, removed: false },
  { id: '3', display_name: 'Former guest', position: 2, removed: true },
  { id: '2', display_name: 'Ben', position: 1, removed: false },
]
let wrapper: VueWrapper | undefined

async function mountForm(amount = '300000') {
  get.mockResolvedValue({ ...trip, members })
  wrapper = (await mountExpenseForm('/trips/abc/expenses/new')).wrapper
  await fillValid(wrapper, amount)
  return wrapper
}

const tiles = (form: VueWrapper) => form.findAll('button[aria-pressed]')
const tileTexts = (form: VueWrapper) => tiles(form).map((tile) => tile.text().replaceAll('\u00a0', ' '))
const tile = (form: VueWrapper, name: string) => {
  const found = tiles(form).find((item) => item.text().includes(name))
  if (!found) throw new Error(`No tile ${name}`)
  return found
}
const chooseMode = (form: VueWrapper, mode: string) => form.get(`input[type="radio"][value="${mode}"]`).setValue(true)
const submit = (form: VueWrapper) => form.get('form').trigger('submit')
const sentSplit = () => (post.mock.calls[0]?.[1] as { split: unknown } | undefined)?.split
const alerts = (form: VueWrapper) => form.findAll('[role="alert"]').map((alert) => alert.text().replaceAll('\u00a0', ' '))

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({ id: 'e1', spent_on: '2026-11-06' })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('participant grid', () => {
  it('orders active members by position and displays equal split preview', async () => {
    const form = await mountForm('100000')
    expect(tileTexts(form)).toEqual(['AAlex₫33,334', 'BBen₫33,333', 'CClara₫33,333'])
    expect(form.text()).toContain('Split between 3 people')
    expect(form.text()).toContain('Tap someone to leave them out or add them back')
  })

  it('toggles a member out and back in with visual muted state', async () => {
    const form = await mountForm()
    await tile(form, 'Ben').trigger('click')
    expect(tile(form, 'Ben').attributes('aria-pressed')).toBe('false')
    expect(tile(form, 'Ben').text()).toContain('Out')
    expect(tile(form, 'Ben').find('[role="img"]').classes()).toContain('text-muted')
    expect(tileTexts(form)).toEqual(['AAlex₫150,000', 'BBenOut', 'CClara₫150,000'])
    expect(form.text()).toContain('Split between 2 people')
    await tile(form, 'Ben').trigger('click')
    expect(tile(form, 'Ben').attributes('aria-pressed')).toBe('true')
  })

  it('submits participants sorted by trip position regardless of toggle order', async () => {
    const form = await mountForm()
    await tile(form, 'Alex').trigger('click')
    await tile(form, 'Ben').trigger('click')
    await tile(form, 'Ben').trigger('click')
    await tile(form, 'Alex').trigger('click')
    await submit(form)
    expect(sentSplit()).toEqual({ mode: 'equal', participants: ['1', '2', '4'] })
  })

  it('requires at least one participant and reports error on submit without disabling button', async () => {
    const form = await mountForm()
    for (const name of ['Alex', 'Ben', 'Clara']) await tile(form, name).trigger('click')
    expect(form.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    await submit(form)
    expect(alerts(form)).toEqual(['Pick at least one person'])
    expect(post).not.toHaveBeenCalled()
  })
})

describe('shares split mode', () => {
  it('defaults everyone to 1 share and steps counts cleanly', async () => {
    const form = await mountForm('400000')
    await chooseMode(form, 'shares')
    await form.get('[aria-label="One share more for Alex"]').trigger('click')
    expect(tileTexts(form)).toEqual(['AAlex₫200,000', 'BBen₫100,000', 'CClara₫100,000'])
    await form.get('[aria-label="One share less for Clara"]').trigger('click')
    expect(form.get('[aria-label="One share less for Clara"]').attributes('disabled')).toBeDefined()
    await submit(form)
    expect(sentSplit()).toEqual({ mode: 'shares', shares: { '1': 2, '2': 1, '4': 0 } })
  })

  it('rejects all-zero share weights on submit', async () => {
    const form = await mountForm()
    await chooseMode(form, 'shares')
    for (const name of ['Alex', 'Ben', 'Clara']) {
      await form.get(`[aria-label="One share less for ${name}"]`).trigger('click')
    }
    await submit(form)
    expect(alerts(form)).toEqual(['Give someone at least one share'])
    expect(post).not.toHaveBeenCalled()
  })
})

describe('percent split mode', () => {
  it('tracks running percentage total and upgrades gap into alert on submit', async () => {
    const form = await mountForm('100000')
    await chooseMode(form, 'percent')
    await field(form, "Alex's percent").setValue('33.33')
    await field(form, "Ben's percent").setValue('33.33')
    expect(form.text().replaceAll('\u00a0', ' ')).toContain('Total 66.66% of 100% · 33.34% short')
    expect(alerts(form)).toEqual([])
    await submit(form)
    expect(alerts(form)).toEqual(['Total 66.66% of 100% · 33.34% short'])
    expect(post).not.toHaveBeenCalled()

    await field(form, "Clara's percent").setValue('33.34')
    expect(alerts(form)).toEqual([])
    expect(tileTexts(form)).toEqual(['AAlex₫33,330', 'BBen₫33,330', 'CClara₫33,340'])
    await submit(form)
    expect(sentSplit()).toEqual({ mode: 'percent', basis_points: { '1': 3_333, '2': 3_333, '4': 3_334 } })
  })

  it('displays excess over 100%', async () => {
    const form = await mountForm()
    await chooseMode(form, 'percent')
    await field(form, "Alex's percent").setValue('60')
    await field(form, "Ben's percent").setValue('50')
    expect(form.text().replaceAll('\u00a0', ' ')).toContain('Total 110% of 100% · 10% over')
  })
})

describe('exact amount split mode', () => {
  it('validates exact sum against expense total and submits minor units', async () => {
    const form = await mountForm('100000')
    await chooseMode(form, 'exact')
    await field(form, "Alex's amount").setValue('70000')
    await field(form, "Ben's amount").setValue('22000')
    await tile(form, 'Clara').trigger('click')
    const text = () => form.text().replaceAll('\u00a0', ' ')
    expect(text()).toContain('Total ₫92,000 of ₫100,000 · ₫8,000 short')
    await field(form, "Ben's amount").setValue('32000')
    expect(text()).toContain('₫2,000 over')
    await submit(form)
    expect(alerts(form)).toEqual(['Total ₫102,000 of ₫100,000 · ₫2,000 over'])
    await field(form, "Ben's amount").setValue('30000')
    await submit(form)
    expect(sentSplit()).toEqual({ mode: 'exact', amounts: { '1': 70_000, '2': 30_000 } })
  })

  it('preserves each split mode values when switching tabs', async () => {
    const form = await mountForm()
    await chooseMode(form, 'exact')
    await field(form, "Alex's amount").setValue('70000')
    await chooseMode(form, 'shares')
    await chooseMode(form, 'exact')
    expect(field(form, "Alex's amount").element).toHaveProperty('value', '70,000')
  })
})
