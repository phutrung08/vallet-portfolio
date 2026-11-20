import { describe, expect, it } from 'vitest'
import type { Contribution } from '@/entities'
import { canTurnOff, memberTotals, newestFirst, readOnlyReason } from '@/features/fund/fundRules'
import { trip } from '@/features/trips/tripFixtures'

function contribution(id: string, contributedOn: string, createdAt: string): Contribution {
  return { id, member_id: '1', amount: 1000, contributed_on: contributedOn, created_by: '1', created_at: createdAt }
}

describe('memberTotals', () => {
  it('lists active members in order with 0 for non-contributors', () => {
    const rows = memberTotals(trip, { members: [{ member_id: '2', contributed: 700 }] })
    expect(rows.map((row) => [row.member.id, row.contributed])).toEqual([
      ['1', 0],
      ['2', 700],
    ])
  })

  it('omits removed members even if they previously contributed', () => {
    const rows = memberTotals(trip, { members: [{ member_id: '3', contributed: 50 }] })
    expect(rows.map((row) => row.member.id)).toEqual(['1', '2'])
  })
})

describe('newestFirst', () => {
  it('sorts descending by date then timestamp without mutating input array', () => {
    const input = [
      contribution('old', '2026-11-01', '2026-11-01T10:00:00Z'),
      contribution('late', '2026-11-05', '2026-11-05T09:00:00Z'),
      contribution('later', '2026-11-05', '2026-11-05T12:00:00Z'),
    ]
    expect(newestFirst(input).map((item) => item.id)).toEqual(['later', 'late', 'old'])
    expect(input[0]?.id).toBe('old')
  })
})

describe('canTurnOff', () => {
  it('returns true only when contributions and spent totals are both empty', () => {
    expect(canTurnOff({ contributions: [], spent: 0 })).toBe(true)
    expect(canTurnOff({ contributions: [], spent: 5 })).toBe(false)
    expect(canTurnOff({ contributions: [contribution('a', '2026-11-01', 'x')], spent: 0 })).toBe(false)
  })
})

describe('readOnlyReason', () => {
  it('prioritises lock notice over closed notice and returns null when writable', () => {
    expect(readOnlyReason({ locked: true, closed: true })).toBe('errors.trip_locked')
    expect(readOnlyReason({ locked: false, closed: true })).toBe('errors.trip_closed')
    expect(readOnlyReason({ locked: false, closed: false })).toBeNull()
  })
})
