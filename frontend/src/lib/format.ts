import type { AppLocale } from '@/lib/i18n'

export type CurrencyCode = 'VND' | 'USD'

export const EXPONENTS: Record<CurrencyCode, number> = { VND: 0, USD: 2 }
export const SYMBOLS: Record<CurrencyCode, string> = { VND: '₫', USD: '$' }

const numberFormats = new Map<string, Intl.NumberFormat>()
const dateFormats = new Map<string, Intl.DateTimeFormat>()

function numberFormat(locale: AppLocale, options: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = `${locale}|${JSON.stringify(options)}`
  let format = numberFormats.get(key)
  if (!format) {
    format = new Intl.NumberFormat(locale, options)
    numberFormats.set(key, format)
  }
  return format
}

function dateFormat(locale: AppLocale, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = `${locale}|${JSON.stringify(options)}`
  let format = dateFormats.get(key)
  if (!format) {
    format = new Intl.DateTimeFormat(locale, options)
    dateFormats.set(key, format)
  }
  return format
}

function toMajor(minor: number, currency: CurrencyCode): number {
  if (!Number.isInteger(minor)) {
    throw new RangeError(`Minor units must be an integer, got ${minor}`)
  }
  return minor / 10 ** EXPONENTS[currency]
}

function currencyOptions(currency: CurrencyCode): Intl.NumberFormatOptions {
  const digits = EXPONENTS[currency]
  return {
    style: 'currency',
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }
}

export function formatMoney(minor: number, currency: CurrencyCode, locale: AppLocale): string {
  return numberFormat(locale, currencyOptions(currency)).format(toMajor(minor, currency))
}

export function formatSignedMoney(
  minor: number,
  currency: CurrencyCode,
  locale: AppLocale,
): string {
  const options = { ...currencyOptions(currency), signDisplay: 'exceptZero' } as const
  return numberFormat(locale, options).format(toMajor(minor, currency))
}

export function formatCompactMoney(
  minor: number,
  currency: CurrencyCode,
  locale: AppLocale,
): string {
  const options = {
    style: 'currency',
    currency,
    notation: 'compact',
    maximumFractionDigits: 1,
  } as const
  return numberFormat(locale, options).format(toMajor(minor, currency))
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

function parseIsoDate(isoDate: string): Date {
  const match = ISO_DATE.exec(isoDate)
  if (!match) throw new RangeError(`Invalid date: ${isoDate}`)
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const date = new Date(Date.UTC(year, month - 1, day))
  const roundTrips =
    date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
  if (!roundTrips) throw new RangeError(`Invalid date: ${isoDate}`)
  return date
}

export function formatDayMonth(isoDate: string, locale: AppLocale): string {
  const options = { day: 'numeric', month: 'numeric', timeZone: 'UTC' } as const
  return dateFormat(locale, options).format(parseIsoDate(isoDate))
}

/** Basis points (10,000 = 100%) formatted for display, e.g. 3333 -> "33.33%". */
export function formatBasisPoints(points: number, locale: AppLocale): string {
  return numberFormat(locale, { style: 'percent', maximumFractionDigits: 2 }).format(points / 10_000)
}

/** Saved snapshot timestamp: "14:05" today or "14:05 12/11" on an earlier day. */
export function formatSavedAt(savedAt: Date, now: Date, locale: AppLocale): string {
  const time = dateFormat(locale, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
  const sameDay = savedAt.toDateString() === now.toDateString()
  if (sameDay) return time.format(savedAt)
  const day = dateFormat(locale, { day: 'numeric', month: 'numeric' })
  return `${time.format(savedAt)} ${day.format(savedAt)}`
}

/** Local clock time formatted in 24-hour style, e.g. "21:40". */
export function formatClock(moment: Date, locale: AppLocale): string {
  return dateFormat(locale, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(moment)
}

/** Local month/day label without year, e.g. "11/6" or "6/11". */
export function formatDayMonthLocal(moment: Date, locale: AppLocale): string {
  return dateFormat(locale, { day: 'numeric', month: 'numeric' }).format(moment)
}
