import { describe, expect, it } from 'vitest'
import { expense } from '@/features/expenses/expenseFixtures'
import {
  buildExpenseBody,
  defaultSpentOn,
  initialForm,
  normaliseText,
  serverFieldErrors,
  splitCandidates,
  validateExpense,
  type ExpenseFormState,
} from '@/features/expenses/expenseFormRules'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError } from '@/lib/api'

const filled: ExpenseFormState = {
  amount: 395_000,
  title: '  Spicy   noodles ',
  spentOn: '2026-11-06',
  category: 'food',
  paidBy: '1',
  note: '',
  place: '',
}

describe('defaultSpentOn', () => {
  const dates = { starts_on: '2026-11-05', ends_on: '2026-11-08' }

  it('selects today when inside trip window including boundaries', () => {
    expect(defaultSpentOn(dates, '2026-11-06')).toBe('2026-11-06')
    expect(defaultSpentOn(dates, '2026-11-05')).toBe('2026-11-05')
    expect(defaultSpentOn(dates, '2026-11-08')).toBe('2026-11-08')
  })

  it('falls back to start date when outside trip window', () => {
    expect(defaultSpentOn(dates, '2026-11-01')).toBe('2026-11-05')
    expect(defaultSpentOn(dates, '2026-11-20')).toBe('2026-11-05')
  })

  it('uses today when no start date is configured', () => {
    expect(defaultSpentOn({ starts_on: null, ends_on: null }, '2026-11-20')).toBe('2026-11-20')
    expect(defaultSpentOn({ starts_on: null, ends_on: '2026-11-01' }, '2026-11-20')).toBe('2026-11-20')
  })
})

describe('initialForm', () => {
  it('defaults to food, computed trip date, and current member as payer', () => {
    expect(initialForm(trip, '2026-11-06')).toEqual({
      amount: null,
      title: '',
      spentOn: '2026-11-06',
      category: 'food',
      paidBy: '1',
      note: '',
      place: '',
    })
  })

  it('hydrates every field when editing an existing expense', () => {
    const stored = expense({ '1': 100 }, { title: 'Taxi', category: 'transport', paid_by: null, note: 'n', place: 'p' })
    expect(initialForm(trip, '2026-11-20', stored)).toEqual({
      amount: 100,
      title: 'Taxi',
      spentOn: '2026-11-05',
      category: 'transport',
      paidBy: null,
      note: 'n',
      place: 'p',
    })
  })
})

describe('validateExpense', () => {
  it('accepts valid state', () => {
    expect(validateExpense(filled)).toEqual({})
  })

  it('validates amount bounds between 1 and 10^12 minor units', () => {
    expect(validateExpense({ ...filled, amount: null }).amount?.key).toBe('amountRequired')
    expect(validateExpense({ ...filled, amount: 0 }).amount?.key).toBe('amountRequired')
    expect(validateExpense({ ...filled, amount: 1 }).amount).toBeUndefined()
    expect(validateExpense({ ...filled, amount: 10 ** 12 }).amount).toBeUndefined()
    expect(validateExpense({ ...filled, amount: 10 ** 12 + 1 }).amount?.key).toBe('amountTooLarge')
  })

  it('validates title presence and 120-codepoint length', () => {
    expect(validateExpense({ ...filled, title: '   ' }).title?.key).toBe('titleRequired')
    expect(validateExpense({ ...filled, title: 'ă'.repeat(120) }).title).toBeUndefined()
    expect(validateExpense({ ...filled, title: 'a'.repeat(121) }).title?.key).toBe('titleTooLong')
  })

  it('enforces 500-char note and 200-char place limits', () => {
    expect(validateExpense({ ...filled, note: 'a'.repeat(500), place: 'b'.repeat(200) })).toEqual({})
    expect(validateExpense({ ...filled, note: 'a'.repeat(501) }).note?.key).toBe('noteTooLong')
    expect(validateExpense({ ...filled, place: 'b'.repeat(201) }).place?.key).toBe('placeTooLong')
  })

  it('requires spentOn date', () => {
    expect(validateExpense({ ...filled, spentOn: '' }).spentOn?.key).toBe('dateRequired')
  })
})

describe('buildExpenseBody', () => {
  it('produces API payload with normalised title', () => {
    expect(buildExpenseBody(filled, { mode: 'equal', participants: ['1', '2'] })).toEqual({
      title: 'Spicy noodles',
      amount: 395_000,
      category: 'food',
      spent_on: '2026-11-06',
      paid_by: '1',
      split: { mode: 'equal', participants: ['1', '2'] },
      note: null,
      place: null,
    })
  })

  it('sends null payer when paid by shared fund', () => {
    expect(buildExpenseBody({ ...filled, paidBy: null }, { mode: 'equal', participants: ['1'] }).paid_by).toBeNull()
  })
})

describe('normaliseText', () => {
  it('normalises CRLF to LF, trims whitespace, and converts empty to null', () => {
    expect(normaliseText('  Dinner\r\nat market  ')).toBe('Dinner\nat market')
    expect(normaliseText('   ')).toBeNull()
  })

  it('forwards normalised note and null empty place into body', () => {
    const body = buildExpenseBody({ ...filled, note: ' Delicious ', place: '' }, { mode: 'equal', participants: ['1'] })
    expect(body).toMatchObject({ note: 'Delicious', place: null })
  })
})

describe('splitCandidates', () => {
  it('lists active members sorted by position', () => {
    const members = [
      { id: 'z', display_name: 'Z', position: 2, removed: false },
      { id: 'x', display_name: 'X', position: 0, removed: false },
      { id: 'y', display_name: 'Y', position: 1, removed: true },
    ]
    expect(splitCandidates({ members }).map((member) => member.id)).toEqual(['x', 'z'])
  })

  it('includes a removed member when already attached to the edited expense', () => {
    const members = [
      { id: 'a', display_name: 'A', position: 0, removed: false },
      { id: 'b', display_name: 'B', position: 1, removed: true },
      { id: 'c', display_name: 'C', position: 2, removed: true },
      { id: 'd', display_name: 'D', position: 3, removed: true },
    ]
    const sharedByB = expense({ a: 50, b: 50 }, { paid_by: 'a' })
    expect(splitCandidates({ members }, sharedByB).map((member) => member.id)).toEqual(['a', 'b'])
    const paidByC = expense({ a: 100 }, { paid_by: 'c' })
    expect(splitCandidates({ members }, paidByC).map((member) => member.id)).toEqual(['a', 'c'])
  })
})

describe('serverFieldErrors', () => {
  it('extracts missing or excess exact-split gap', () => {
    const missing = new ApiError(422, 'invalid_split', 'x', undefined, [], 8_000)
    expect(serverFieldErrors(missing)).toEqual({ split: { key: 'missing', amount: 8_000 } })
    const excess = new ApiError(422, 'invalid_split', 'x', undefined, [], -2_000)
    expect(serverFieldErrors(excess)).toEqual({ split: { key: 'excess', amount: 2_000 } })
    expect(serverFieldErrors(new ApiError(422, 'invalid_split', 'x'))).toEqual({
      split: { key: 'invalid' },
    })
  })

  it('maps Pydantic field paths onto form field slots', () => {
    const error = new ApiError(422, 'validation_error', 'x', undefined, [
      'body.title',
      'body.amount',
      'body.spent_on',
      'body.paid_by',
      'body.split.equal.participants',
      'body.note',
      'body.place',
      'body.unknown',
    ])
    expect(Object.keys(serverFieldErrors(error)).sort()).toEqual([
      'amount',
      'note',
      'paidBy',
      'place',
      'spentOn',
      'split',
      'title',
    ])
  })

  it('leaves non-validation errors for the form banner', () => {
    expect(serverFieldErrors(new ApiError(409, 'no_fund', 'x'))).toEqual({})
    expect(serverFieldErrors(new Error('boom'))).toEqual({})
  })
})
