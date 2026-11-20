import type { Expense, ExpenseCategory, TripDetail, TripMember } from '@/entities'
import { MAX_AMOUNT } from '@/features/expenses/amountText'
import type { SplitRequest } from '@/features/expenses/splitDraft'
import { normaliseName } from '@/features/trips/tripFormRules'
import { includesToday } from '@/features/trips/tripMeta'
import { ApiError } from '@/lib/api'

export const MAX_TITLE = 120
export const MAX_NOTE = 500
export const MAX_PLACE = 200

export const CATEGORIES: readonly ExpenseCategory[] = [
  'food',
  'transport',
  'lodging',
  'activity',
  'shopping',
  'other',
]

export type ErrorKey =
  | 'amountRequired'
  | 'amountTooLarge'
  | 'titleRequired'
  | 'titleTooLong'
  | 'dateRequired'
  | 'invalid'
  | 'missing'
  | 'excess'
  | 'noParticipants'
  | 'sharesZero'
  | 'noteTooLong'
  | 'placeTooLong'

export type Field = 'amount' | 'title' | 'spentOn' | 'category' | 'paidBy' | 'split' | 'note' | 'place'

/** Message key with optional minor-unit amount or basis-point percent gap. */
export interface FieldMessage {
  key: ErrorKey
  amount?: number
  percent?: number
}

export type FormErrors = Partial<Record<Field, FieldMessage>>

export interface ExpenseFormState {
  amount: number | null
  title: string
  spentOn: string
  category: ExpenseCategory
  /** Paying member ID, or null when the shared fund paid. */
  paidBy: string | null
  note: string
  place: string
}

export interface ExpenseRequest {
  title: string
  amount: number
  category: ExpenseCategory
  spent_on: string
  paid_by: string | null
  split: SplitRequest
  note: string | null
  place: string | null
}

/** Today if inside trip dates, else trip start date, else today. */
export function defaultSpentOn(trip: Pick<TripDetail, 'starts_on' | 'ends_on'>, today: string): string {
  if (includesToday(trip, today)) return today
  return trip.starts_on ?? today
}

/** Initializes a fresh expense form or hydrates one from an existing expense. */
export function initialForm(trip: TripDetail, today: string, expense?: Expense): ExpenseFormState {
  if (expense) {
    return {
      amount: expense.amount,
      title: expense.title,
      spentOn: expense.spent_on,
      category: expense.category,
      paidBy: expense.paid_by,
      note: expense.note ?? '',
      place: expense.place ?? '',
    }
  }
  return {
    amount: null,
    title: '',
    spentOn: defaultSpentOn(trip, today),
    category: 'food',
    paidBy: trip.me,
    note: '',
    place: '',
  }
}

/** Normalises multiline free text matching backend sanitization; blank returns null. */
export function normaliseText(raw: string): string | null {
  return raw.replace(/\r\n/g, '\n').normalize('NFC').trim() || null
}

function tooLong(raw: string, max: number): boolean {
  return [...(normaliseText(raw) ?? '')].length > max
}

export function validateExpense(form: ExpenseFormState): FormErrors {
  const errors: FormErrors = {}
  if (form.amount === null || form.amount < 1) errors.amount = { key: 'amountRequired' }
  else if (form.amount > MAX_AMOUNT) errors.amount = { key: 'amountTooLarge' }
  const title = normaliseName(form.title)
  if (title === '') errors.title = { key: 'titleRequired' }
  else if ([...title].length > MAX_TITLE) errors.title = { key: 'titleTooLong' }
  if (form.spentOn === '') errors.spentOn = { key: 'dateRequired' }
  if (tooLong(form.note, MAX_NOTE)) errors.note = { key: 'noteTooLong' }
  if (tooLong(form.place, MAX_PLACE)) errors.place = { key: 'placeTooLong' }
  return errors
}

/**
 * Members eligible as payer or split participant, sorted by position: active members plus
 * any removed member already attached to the expense being edited.
 */
export function splitCandidates(trip: Pick<TripDetail, 'members'>, expense?: Expense): TripMember[] {
  const onExpense = new Set(expense?.shares.map((share) => share.member_id))
  if (expense?.paid_by) onExpense.add(expense.paid_by)
  return trip.members
    .filter((member) => !member.removed || onExpense.has(member.id))
    .sort((a, b) => a.position - b.position)
}

/** Builds the expense request body; call only after `validateExpense` passes. */
export function buildExpenseBody(form: ExpenseFormState, split: SplitRequest): ExpenseRequest {
  return {
    title: normaliseName(form.title),
    amount: form.amount ?? 0,
    category: form.category,
    spent_on: form.spentOn,
    paid_by: form.paidBy,
    split,
    note: normaliseText(form.note),
    place: normaliseText(form.place),
  }
}

const FIELD_OF_PARAM: Record<string, Field> = {
  title: 'title',
  amount: 'amount',
  category: 'category',
  spent_on: 'spentOn',
  paid_by: 'paidBy',
  split: 'split',
  note: 'note',
  place: 'place',
}

function differenceMessage(difference: number | undefined): FieldMessage {
  if (difference === undefined || difference === 0) return { key: 'invalid' }
  return difference > 0 ? { key: 'missing', amount: difference } : { key: 'excess', amount: -difference }
}

/** Maps 422 `validation_error` paths and `invalid_split` differences to form field errors. */
export function serverFieldErrors(error: unknown): FormErrors {
  if (!(error instanceof ApiError)) return {}
  if (error.code === 'invalid_split') {
    return { split: differenceMessage(error.difference) }
  }
  if (error.code !== 'validation_error') return {}
  const errors: FormErrors = {}
  for (const path of error.fields) {
    const field = FIELD_OF_PARAM[path.split('.')[1] ?? '']
    if (field) errors[field] = { key: 'invalid' }
  }
  return errors
}
