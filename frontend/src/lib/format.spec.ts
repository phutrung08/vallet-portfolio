import { describe, expect, it } from 'vitest'
import {
  formatBasisPoints,
  formatClock,
  formatCompactMoney,
  formatDayMonth,
  formatDayMonthLocal,
  formatMoney,
  formatSavedAt,
  formatSignedMoney,
} from '@/lib/format'

const plain = (text: string) => text.replaceAll(' ', ' ')

describe('formatMoney', () => {
  it.each([
    [28614000, 'VND', 'vi', '28.614.000 ₫'],
    [-2386183, 'VND', 'vi', '-2.386.183 ₫'],
    [0, 'VND', 'vi', '0 ₫'],
    [123456, 'USD', 'en', '$1,234.56'],
    [5, 'USD', 'en', '$0.05'],
    [-123456, 'USD', 'en', '-$1,234.56'],
    [0, 'USD', 'en', '$0.00'],
  ] as const)('%i %s %s -> %s', (minor, currency, locale, expected) => {
    expect(plain(formatMoney(minor, currency, locale))).toBe(expected)
  })

  it.each([1.5, Number.NaN, Infinity])('rejects non-integer minor %s', (minor) => {
    expect(() => formatMoney(minor, 'VND', 'en')).toThrow(RangeError)
  })
})

describe('formatSignedMoney', () => {
  it.each([
    [3694817, 'VND', 'vi', '+3.694.817 ₫'],
    [-2386183, 'VND', 'vi', '-2.386.183 ₫'],
    [0, 'VND', 'vi', '0 ₫'],
    [123456, 'USD', 'en', '+$1,234.56'],
    [0, 'USD', 'en', '$0.00'],
  ] as const)('%i %s %s -> %s', (minor, currency, locale, expected) => {
    expect(plain(formatSignedMoney(minor, currency, locale))).toBe(expected)
  })

  it('rejects non-integer minor', () => {
    expect(() => formatSignedMoney(0.5, 'VND', 'en')).toThrow(RangeError)
  })
})

describe('formatCompactMoney', () => {
  it.each([
    [14750000, 'VND', 'vi', '14,8 Tr ₫'],
    [14750000, 'VND', 'en', '₫14.8M'],
  ] as const)('%i %s %s -> %s', (minor, currency, locale, expected) => {
    expect(plain(formatCompactMoney(minor, currency, locale))).toBe(expected)
  })

  it('rejects non-integer minor', () => {
    expect(() => formatCompactMoney(0.5, 'VND', 'en')).toThrow(RangeError)
  })
})

describe('formatDayMonth', () => {
  it.each([
    ['2026-11-05', 'vi', '5/11'],
    ['2026-11-05', 'en', '11/5'],
    ['2026-01-01', 'vi', '1/1'],
    ['2028-02-29', 'vi', '29/2'],
  ] as const)('%s %s -> %s', (iso, locale, expected) => {
    expect(formatDayMonth(iso, locale)).toBe(expected)
  })

  it.each(['America/Los_Angeles', 'Pacific/Kiritimati'])(
    'does not shift the day in a distant timezone (%s)',
    (zone) => {
      const original = process.env.TZ
      process.env.TZ = zone
      try {
        expect(formatDayMonth('2026-11-05', 'en')).toBe('11/5')
      } finally {
        process.env.TZ = original
      }
    },
  )

  it.each(['2026-02-30', '2027-02-29', '2026-13-01', '2026-00-10', '2026-11-5', '5/11/2026', ''])(
    'rejects invalid date %j',
    (iso) => {
      expect(() => formatDayMonth(iso, 'en')).toThrow(RangeError)
    },
  )
})

describe('formatBasisPoints', () => {
  it('shows basis points as a percent with up to two decimals', () => {
    expect(formatBasisPoints(3_333, 'vi')).toBe('33,33%')
    expect(formatBasisPoints(10_000, 'en')).toBe('100%')
    expect(formatBasisPoints(50, 'en')).toBe('0.5%')
  })
})

describe('formatSavedAt and local moment formatters', () => {
  const now = new Date(2026, 10, 16, 18, 0)

  it('shows only the time for a copy saved today', () => {
    expect(formatSavedAt(new Date(2026, 10, 16, 7, 5), now, 'vi')).toBe('07:05')
    expect(formatSavedAt(new Date(2026, 10, 16, 14, 30), now, 'en')).toBe('14:30')
  })

  it('adds the day for an older copy', () => {
    expect(formatSavedAt(new Date(2026, 10, 12, 21, 40), now, 'vi')).toBe('21:40 12/11')
  })

  it('formats 24h clock and local day-month', () => {
    const sample = new Date(2026, 10, 6, 9, 4)
    expect(formatClock(sample, 'en')).toBe('09:04')
    expect(formatDayMonthLocal(sample, 'vi')).toBe('6/11')
  })
})
