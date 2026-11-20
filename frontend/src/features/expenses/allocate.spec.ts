import { describe, expect, it } from 'vitest'
import { allocate } from '@/features/expenses/allocate'

// Mirrors backend allocation boundary cases in domain/test_money.py and test_split.py.
describe('allocate matches backend', () => {
  it.each([
    [130_000, [1, 1, 1, 1, 1, 1], [21_667, 21_667, 21_667, 21_667, 21_666, 21_666]],
    [850_000, [1, 1, 1, 1, 1, 1], [141_667, 141_667, 141_667, 141_667, 141_666, 141_666]],
    [708_000, [1, 1, 1, 1, 0, 1], [141_600, 141_600, 141_600, 141_600, 0, 141_600]],
    [359_000, [1, 0, 0, 1, 1, 1], [89_750, 0, 0, 89_750, 89_750, 89_750]],
    [100, [1, 1, 1], [34, 33, 33]],
    [0, [1, 2, 3], [0, 0, 0]],
    [0, [0, 0], [0, 0]],
    [123_456, [7], [123_456]],
    [300_000, [2, 1], [200_000, 100_000]],
    [100, [1, 0, 1], [50, 0, 50]],
    [3_800_000, [588, 724, 724, 588, 588, 588], [588_000, 724_000, 724_000, 588_000, 588_000, 588_000]],
    [100_000, [3_333, 3_333, 3_334], [33_330, 33_330, 33_340]],
    [101, [3_333, 3_333, 3_334], [34, 33, 34]],
    [200_000, [5_000, 5_000], [100_000, 100_000]],
    [100, [10_000, 0], [100, 0]],
  ])('%d over %j -> %j', (total, weights, expected) => {
    expect(allocate(total, weights)).toEqual(expected)
  })

  it.each([
    [5, [1, 1, 1, 1], [2, 1, 1, 1]],
    [2, [1, 1, 1, 1], [1, 1, 0, 0]],
    [10, [1, 2, 1, 2], [2, 3, 2, 3]],
    [3, [0, 1, 1, 1, 1], [0, 1, 1, 1, 0]],
  ])('breaks remainder ties to lower index: %d over %j', (total, weights, expected) => {
    expect(allocate(total, weights)).toEqual(expected)
  })

  it('stays exact when total * weight exceeds 2^53', () => {
    expect(allocate(999_999_999_999, [9_999, 1])).toEqual([999_899_999_999, 100_000_000])
    expect(allocate(10 ** 12, [10_000, 10_000, 10_000])).toEqual([
      333_333_333_334, 333_333_333_333, 333_333_333_333,
    ])
    const parts = allocate(10 ** 12 - 1, [9_973, 9_967, 9_949, 7])
    expect(parts.reduce((sum, part) => sum + part, 0)).toBe(10 ** 12 - 1)
  })

  it('sums to total with every share within 1 unit of its exact quota', () => {
    for (const total of [1, 7, 99_999, 123_456_789]) {
      for (const weights of [[1], [1, 2, 3], [3_333, 3_333, 3_334], [0, 5, 0, 5]]) {
        const parts = allocate(total, weights)
        const sum = weights.reduce((a, b) => a + b, 0)
        expect(parts.reduce((a, b) => a + b, 0)).toBe(total)
        parts.forEach((part, i) => expect(Math.abs(part - (total * (weights[i] ?? 0)) / sum)).toBeLessThan(1))
      }
    }
  })

  it.each([
    [-1, [1]],
    [100, []],
    [100, [1, -1]],
    [100, [0, 0]],
    [1.5, [1]],
  ])('rejects invalid inputs (%d over %j)', (total, weights) => {
    expect(() => allocate(total, weights)).toThrow(RangeError)
  })
})
