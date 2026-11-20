import type { AppLocale } from '@/lib/i18n'

export const MAX_AMOUNT = 10 ** 12
// Caps pasted digit runs before conversion into BigInt.
const MAX_INTEGER_DIGITS = 15

interface Separators {
  group: string
  decimal: string
}

const separatorCache = new Map<AppLocale, Separators>()

function separators(locale: AppLocale): Separators {
  let found = separatorCache.get(locale)
  if (!found) {
    const parts = new Intl.NumberFormat(locale).formatToParts(1234.5)
    found = {
      group: parts.find((part) => part.type === 'group')?.value ?? ',',
      decimal: parts.find((part) => part.type === 'decimal')?.value ?? '.',
    }
    separatorCache.set(locale, found)
  }
  return found
}

function groupDigits(digits: string, group: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, group)
}

/**
 * Normalises typed numeric input for display with locale thousands separators and at most
 * `exponent` fractional digits (0 for VND, 2 for USD cents or basis-point percents).
 */
export function normaliseAmountText(raw: string, exponent: number, locale: AppLocale): string {
  const { group, decimal } = separators(locale)
  const decimalAt = exponent > 0 ? raw.indexOf(decimal) : -1
  const integerRaw = decimalAt === -1 ? raw : raw.slice(0, decimalAt)
  const integer = integerRaw
    .replace(/\D/g, '')
    .replace(/^0+(?=\d)/, '')
    .slice(0, MAX_INTEGER_DIGITS)
  if (decimalAt === -1) return groupDigits(integer, group)
  const fraction = raw
    .slice(decimalAt + 1)
    .replace(/\D/g, '')
    .slice(0, exponent)
  return `${groupDigits(integer || '0', group)}${decimal}${fraction}`
}

/** Parses display text into exact integer units of 10^-exponent without floating-point drift. */
export function parseAmountText(text: string, exponent: number, locale: AppLocale): number | null {
  const { group, decimal } = separators(locale)
  const cleaned = text.trim().split(group).join('')
  const pieces = exponent > 0 ? cleaned.split(decimal) : [cleaned]
  const [integer = '', fraction = ''] = pieces
  const wellFormed =
    pieces.length <= 2 &&
    /^\d*$/.test(integer) &&
    /^\d*$/.test(fraction) &&
    fraction.length <= exponent &&
    integer.length <= MAX_INTEGER_DIGITS
  if (!wellFormed || integer + fraction === '') return null
  const minor =
    BigInt(integer || '0') * 10n ** BigInt(exponent) + BigInt(fraction.padEnd(exponent, '0') || '0')
  return Number(minor)
}

/** Formats minor units back into input text, e.g. 1250 at exponent 2 -> "12.50" in English. */
export function formatAmountText(minor: number, exponent: number, locale: AppLocale): string {
  const { group, decimal } = separators(locale)
  const digits = String(minor).padStart(exponent + 1, '0')
  const integer = groupDigits(digits.slice(0, digits.length - exponent), group)
  return exponent === 0 ? integer : `${integer}${decimal}${digits.slice(digits.length - exponent)}`
}

/** Counts significant digits and decimal separators before `index` (ignoring thousands separators). */
export function significantBefore(text: string, index: number, locale: AppLocale): number {
  const { decimal } = separators(locale)
  return [...text.slice(0, index)].filter((char) => /\d/.test(char) || char === decimal).length
}

/** Finds the caret index in `text` right after `count` significant characters. */
export function caretAfter(text: string, count: number, locale: AppLocale): number {
  if (count === 0) return 0
  const { decimal } = separators(locale)
  let seen = 0
  for (let index = 0; index < text.length; index += 1) {
    const char = text.charAt(index)
    if (/\d/.test(char) || char === decimal) seen += 1
    if (seen === count) return index + 1
  }
  return text.length
}
