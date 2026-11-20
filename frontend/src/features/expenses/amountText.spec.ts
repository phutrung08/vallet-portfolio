import { describe, expect, it } from 'vitest'
import {
  MAX_AMOUNT,
  caretAfter,
  formatAmountText,
  normaliseAmountText,
  parseAmountText,
  significantBefore,
} from '@/features/expenses/amountText'

describe('normaliseAmountText', () => {
  it.each([
    ['395000', '395.000'],
    ['395.0001', '3.950.001'],
    ['0012', '12'],
    ['12a3,4', '1.234'],
    ['', ''],
  ])('groups VND thousands in Vietnamese: %s -> %s', (raw, expected) => {
    expect(normaliseAmountText(raw, 0, 'vi')).toBe(expected)
  })

  it('groups with commas in English', () => {
    expect(normaliseAmountText('1234567', 0, 'en')).toBe('1,234,567')
  })

  it.each([
    ['1234.5', '1,234.5'],
    ['12.', '12.'],
    ['.5', '0.5'],
    ['12.345', '12.34'],
    ['1.2.3', '1.23'],
  ])('retains up to two decimals for USD in English: %s -> %s', (raw, expected) => {
    expect(normaliseAmountText(raw, 2, 'en')).toBe(expected)
  })

  it('uses comma decimal separator in Vietnamese', () => {
    expect(normaliseAmountText('1234,56', 2, 'vi')).toBe('1.234,56')
  })

  it('bounds pasted integer digit length', () => {
    expect(normaliseAmountText('9'.repeat(40), 0, 'en').replace(/,/g, '')).toHaveLength(15)
  })
})

describe('parseAmountText', () => {
  it.each([
    ['395.000', 0, 'vi', 395_000],
    ['1,234', 0, 'en', 1_234],
    ['12.34', 2, 'en', 1_234],
    ['12.3', 2, 'en', 1_230],
    ['12.', 2, 'en', 1_200],
    ['0.07', 2, 'en', 7],
    ['1.234,56', 2, 'vi', 123_456],
  ] as const)('%s at exponent %d (%s) -> %d', (text, exponent, locale, expected) => {
    expect(parseAmountText(text, exponent, locale)).toBe(expected)
  })

  it('avoids floating-point inaccuracy on decimal inputs', () => {
    expect(parseAmountText('0.29', 2, 'en')).toBe(29)
    expect(parseAmountText('19.99', 2, 'en')).toBe(1_999)
    expect(parseAmountText('9,999,999,999.99', 2, 'en')).toBe(999_999_999_999)
  })

  it('parses boundary amounts accurately', () => {
    expect(parseAmountText('1.000.000.000.000', 0, 'vi')).toBe(MAX_AMOUNT)
    expect(parseAmountText('10,000,000,000.00', 2, 'en')).toBe(MAX_AMOUNT)
    expect(parseAmountText('1.000.000.000.001', 0, 'vi')).toBe(MAX_AMOUNT + 1)
    expect(parseAmountText('0.01', 2, 'en')).toBe(1)
    expect(parseAmountText('0', 0, 'vi')).toBe(0)
  })

  it.each([
    ['', 0],
    ['  ', 0],
    ['1.2.3', 2],
    ['1.234', 2],
    ['12a', 0],
    ['.', 2],
  ] as const)('returns null for malformed input %j (exponent %d)', (text, exponent) => {
    expect(parseAmountText(text, exponent, 'en')).toBeNull()
  })
})

describe('percent basis points', () => {
  it('parses up to two decimals accurately', () => {
    expect(parseAmountText('33,33', 2, 'vi')).toBe(3_333)
    expect(parseAmountText('100', 2, 'vi')).toBe(10_000)
    expect(parseAmountText('0.01', 2, 'en')).toBe(1)
  })
})

describe('formatAmountText', () => {
  it('formats grouped VND and fixed two-decimal USD', () => {
    expect(formatAmountText(395_000, 0, 'vi')).toBe('395.000')
    expect(formatAmountText(1_250, 2, 'en')).toBe('12.50')
    expect(formatAmountText(7, 2, 'en')).toBe('0.07')
    expect(formatAmountText(123_456, 2, 'vi')).toBe('1.234,56')
  })

  it('round-trips cleanly with parseAmountText', () => {
    for (const minor of [1, 99, 100, 123_456_789, MAX_AMOUNT]) {
      expect(parseAmountText(formatAmountText(minor, 2, 'en'), 2, 'en')).toBe(minor)
      expect(parseAmountText(formatAmountText(minor, 0, 'vi'), 0, 'vi')).toBe(minor)
    }
  })
})

describe('caret helpers', () => {
  it('preserves caret placement across grouping separator insertion', () => {
    const count = significantBefore('39.5000', 6, 'vi')
    expect(count).toBe(5)
    expect(caretAfter('395.000', count, 'vi')).toBe(6)
    expect(caretAfter('395.000', 0, 'vi')).toBe(0)
    expect(caretAfter('12', 9, 'vi')).toBe(2)
  })
})
