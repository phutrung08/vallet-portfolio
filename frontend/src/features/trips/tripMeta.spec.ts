import { describe, expect, it } from 'vitest'
import { activeMemberCount, spentPercent } from '@/features/trips/tripMeta'

describe('spentPercent', () => {
  it.each([
    [10_000_000, 2_500_000, 25],
    [10_000_000, 10_000_000, 100],
    [10_000_000, 12_000_000, 100],
    [10_000_000, 0, 0],
    [0, 500, 100],
    [0, 0, 0],
  ])('contributed %i, spent %i -> %i%%', (contributed, spent, expected) => {
    expect(spentPercent(contributed, spent)).toBe(expected)
  })
})

describe('activeMemberCount', () => {
  it('excludes removed members from active count', () => {
    const members = [
      { id: '1', display_name: 'Alex', position: 0, removed: false },
      { id: '2', display_name: 'Ben', position: 1, removed: true },
    ]
    expect(activeMemberCount({ members })).toBe(1)
  })
})
