import { describe, expect, it } from 'vitest'
import { defaultDay, tripDayNumber } from '@/features/expenses/dayTabs'

describe('tripDayNumber', () => {
  it.each([
    ['2026-11-05', '2026-11-05', 1],
    ['2026-11-08', '2026-11-05', 4],
    ['2026-12-02', '2026-11-30', 3],
    ['2026-11-04', '2026-11-05', null],
    ['2026-11-05', null, null],
  ])('%s relative to %s is %s', (date, start, expected) => {
    expect(tripDayNumber(date, start)).toBe(expected)
  })
})

describe('defaultDay', () => {
  const days = [
    { date: '2026-11-07', count: 1, total: 1 },
    { date: '2026-11-06', count: 1, total: 1 },
  ]

  it('prefers today when recorded', () => {
    expect(defaultDay(days, '2026-11-06')).toBe('2026-11-06')
  })

  it('falls back to the newest recorded day', () => {
    expect(defaultDay(days, '2026-11-20')).toBe('2026-11-07')
  })

  it('returns null when empty', () => {
    expect(defaultDay([], '2026-11-06')).toBeNull()
  })
})
