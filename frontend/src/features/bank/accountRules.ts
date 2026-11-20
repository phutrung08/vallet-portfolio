import type { Bank } from '@/entities'

export const ACCOUNT_NUMBER_MIN = 6
export const ACCOUNT_NUMBER_MAX = 19
export const ACCOUNT_NAME_MAX = 50

const ACCOUNT_NAME = /^[A-Z]+(?: [A-Z]+)*$/

export type AccountFormError = 'bankRequired' | 'numberInvalid' | 'nameInvalid'
export type AccountFormErrors = Partial<Record<'bank' | 'number' | 'name', AccountFormError>>

/** Strips combining diacritics including Vietnamese stroked D/d (`Đ`/`đ`). */
export function stripDiacritics(text: string): string {
  return text.replaceAll('đ', 'd').replaceAll('Đ', 'D').normalize('NFD').replace(/\p{M}/gu, '')
}

/** Filters to digits only, capped at the 19-digit bank account maximum. */
export function digitsOnly(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, ACCOUNT_NUMBER_MAX)
}

/** Uppercases and folds diacritics while typing, matching printed recipient card format. */
export function typedAccountName(raw: string): string {
  return stripDiacritics(raw).toUpperCase().replace(/\s+/g, ' ').trimStart()
}

/** Produces the persisted recipient name without leading/trailing whitespace. */
export function finalAccountName(raw: string): string {
  return typedAccountName(raw).trim()
}

export function validateAccount(form: {
  bin: string | null
  number: string
  name: string
}): AccountFormErrors {
  const errors: AccountFormErrors = {}
  if (form.bin === null) errors.bank = 'bankRequired'
  if (form.number.length < ACCOUNT_NUMBER_MIN || form.number.length > ACCOUNT_NUMBER_MAX) {
    errors.number = 'numberInvalid'
  }
  const name = finalAccountName(form.name)
  if (name.length > ACCOUNT_NAME_MAX || !ACCOUNT_NAME.test(name)) errors.name = 'nameInvalid'
  return errors
}

function fold(text: string): string {
  return stripDiacritics(text).toLowerCase()
}

/** Matches banks by short name or code, ignoring case and diacritics. */
export function filterBanks(banks: readonly Bank[], query: string): Bank[] {
  const needle = fold(query.trim())
  if (needle === '') return [...banks]
  return banks.filter((bank) => fold(bank.short_name).includes(needle) || fold(bank.code).includes(needle))
}
