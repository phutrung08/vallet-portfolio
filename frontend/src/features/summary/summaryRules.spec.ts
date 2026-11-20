import { describe, expect, it } from 'vitest'
import { percentsOf } from '@/features/summary/summaryRules'

const sum = (values: readonly number[]) => values.reduce((total, value) => total + value, 0)

describe('percentsOf', () => {
  it('adds up to exactly 100 when thirds do not divide evenly', () => {
    const percents = percentsOf([1, 1, 1])
    expect(sum(percents)).toBe(100)
    expect([...percents].sort((a, b) => a - b)).toEqual([33, 33, 34])
  })

  it('gives the leftover points to the largest fractional parts', () => {
    expect(percentsOf([500, 300, 150, 50])).toEqual([50, 30, 15, 5])
    expect(percentsOf([6, 5, 5])).toEqual([38, 31, 31])
  })

  it.each([[[7, 11, 13, 17, 19]], [[1, 2, 3, 4, 5, 6]], [[999_999, 1]], [[100]]])(
    'adds up to 100 for %j',
    (amounts) => {
      expect(sum(percentsOf(amounts))).toBe(100)
    },
  )

  it('returns zeros when no positive amounts are present', () => {
    expect(percentsOf([0, 0])).toEqual([0, 0])
    expect(percentsOf([])).toEqual([])
  })
})
