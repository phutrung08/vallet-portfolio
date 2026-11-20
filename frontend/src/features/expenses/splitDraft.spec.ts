import { describe, expect, it } from 'vitest'
import type { SplitMode, TripMember } from '@/entities'
import { allocate } from '@/features/expenses/allocate'
import { expense } from '@/features/expenses/expenseFixtures'
import {
  buildSplit,
  draftFromExpense,
  initialDraft,
  participants,
  previewAmounts,
  splitProblem,
  toggled,
  weightTotal,
  type SplitDraft,
} from '@/features/expenses/splitDraft'

const six: TripMember[] = ['alex', 'ben', 'claire', 'dan', 'emma', 'frank'].map((id, position) => ({
  id,
  display_name: id,
  position,
  removed: false,
}))
// Listed out of position order to confirm sorting strictly follows position.
const shuffled = [six[3], six[0], six[5], six[1], six[4], six[2]].filter((m): m is TripMember => !!m)
const ids = (members: readonly TripMember[]) => members.map((member) => member.id)

function draft(overrides: Partial<SplitDraft> = {}): SplitDraft {
  return { ...initialDraft(six), ...overrides }
}

describe('initialDraft and toggling', () => {
  it('selects all active members in equal mode', () => {
    const withRemoved = [...six, { id: 'gone', display_name: 'x', position: 6, removed: true }]
    expect(initialDraft(withRemoved)).toEqual({
      mode: 'equal',
      included: ids(six),
      shares: {},
      basisPoints: {},
      amounts: {},
    })
  })

  it('toggles a member out and back in', () => {
    expect(toggled(['a', 'b'], 'a')).toEqual(['b'])
    expect(toggled(['b'], 'a')).toEqual(['b', 'a'])
  })

  it('orders participants by trip position regardless of tap sequence', () => {
    const tapped = draft({ included: ['frank', 'alex', 'claire'] })
    expect(ids(participants(tapped, shuffled))).toEqual(['alex', 'claire', 'frank'])
  })
})

describe('draftFromExpense', () => {
  const stored = (mode: SplitMode, weights: Record<string, number>) =>
    expense({}, {
      split_mode: mode,
      shares: Object.entries(weights).map(([member_id, weight]) => ({ member_id, weight, amount: 0 })),
    })

  it.each([
    ['equal', { alex: 1, claire: 1 }, {}, {}, {}],
    ['shares', { alex: 2, claire: 0 }, { alex: 2, claire: 0 }, {}, {}],
    ['percent', { alex: 6_000, claire: 4_000 }, {}, { alex: 6_000, claire: 4_000 }, {}],
    ['exact', { alex: 70_000, claire: 30_000 }, {}, {}, { alex: 70_000, claire: 30_000 }],
  ] as const)('reconstructs %s draft inputs from stored weights', (mode, weights, shares, basisPoints, amounts) => {
    expect(draftFromExpense(stored(mode, weights))).toEqual({
      mode,
      included: ['alex', 'claire'],
      shares,
      basisPoints,
      amounts,
    })
  })

  it('round-trips a pre-filled percent draft back into API split payload', () => {
    const percent = stored('percent', { alex: 6_000, claire: 4_000 })
    expect(buildSplit(draftFromExpense(percent), six)).toEqual({
      mode: 'percent',
      basis_points: { alex: 6_000, claire: 4_000 },
    })
  })
})

describe('previewAmounts matches backend allocation', () => {
  it('equal: distributes extra minor units to lowest positions', () => {
    const preview = previewAmounts(draft({ included: ids(shuffled) }), shuffled, 130_000)
    expect([...(preview ?? [])]).toEqual([
      ['alex', 21_667],
      ['ben', 21_667],
      ['claire', 21_667],
      ['dan', 21_667],
      ['emma', 21_666],
      ['frank', 21_666],
    ])
  })

  it('equal: splits strictly across included participants', () => {
    const preview = previewAmounts(draft({ included: ['alex', 'dan', 'emma', 'frank'] }), six, 359_000)
    expect([...(preview?.values() ?? [])]).toEqual([89_750, 89_750, 89_750, 89_750])
  })

  it('shares: defaults unset participants to 1 share', () => {
    const shares = draft({ mode: 'shares', included: ['alex', 'ben'], shares: { alex: 2 } })
    expect([...(previewAmounts(shares, six, 300_000)?.values() ?? [])]).toEqual([200_000, 100_000])
  })

  it('shares: matches real multi-weight proportional distribution', () => {
    const weights = [588, 724, 724, 588, 588, 588]
    const shares = Object.fromEntries(six.map((member, i) => [member.id, weights[i] ?? 0]))
    const preview = previewAmounts(draft({ mode: 'shares', shares }), shuffled, 3_800_000)
    expect([...(preview?.values() ?? [])]).toEqual(allocate(3_800_000, weights))
    expect([...(preview?.values() ?? [])]).toEqual([588_000, 724_000, 724_000, 588_000, 588_000, 588_000])
  })

  it.each([
    [100_000, [33_330, 33_330, 33_340]],
    [101, [34, 33, 34]],
  ])('percent: allocates %d across 33.33/33.33/33.34%%', (amount, expected) => {
    const percent = draft({
      mode: 'percent',
      included: ['claire', 'ben', 'alex'],
      basisPoints: { alex: 3_333, ben: 3_333, claire: 3_334 },
    })
    expect([...(previewAmounts(percent, six, amount)?.values() ?? [])]).toEqual(expected)
  })

  it('exact: displays typed amounts once total matches', () => {
    const amounts = { alex: 588_000, ben: 724_000, claire: 724_000, dan: 588_000, emma: 588_000, frank: 588_000 }
    const exact = draft({ mode: 'exact', amounts })
    expect([...(previewAmounts(exact, six, 3_800_000)?.values() ?? [])]).toEqual(Object.values(amounts))
    expect(previewAmounts(exact, six, 3_900_000)).toBeNull()
  })

  it('maintains precision at large 10^12 bounds above 2^53', () => {
    const shares = draft({ mode: 'shares', included: ['alex', 'ben'], shares: { alex: 9_999, ben: 1 } })
    expect([...(previewAmounts(shares, six, 999_999_999_999)?.values() ?? [])]).toEqual([
      999_899_999_999, 100_000_000,
    ])
    const max = previewAmounts(draft({ included: ['alex', 'ben', 'claire'] }), six, 10 ** 12)
    expect([...(max?.values() ?? [])]).toEqual([333_333_333_334, 333_333_333_333, 333_333_333_333])
  })

  it('returns null without a valid amount or complete split', () => {
    expect(previewAmounts(draft(), six, null)).toBeNull()
    expect(previewAmounts(draft({ included: [] }), six, 100)).toBeNull()
    expect(previewAmounts(draft({ mode: 'percent', basisPoints: { alex: 5_000 } }), six, 100)).toBeNull()
  })
})

describe('buildSplit', () => {
  it('equal: emits participant IDs in position order', () => {
    expect(buildSplit(draft({ included: ['claire', 'alex'] }), shuffled)).toEqual({
      mode: 'equal',
      participants: ['alex', 'claire'],
    })
  })

  it('shares: defaults unset to 1 and keeps explicit zero weights', () => {
    const shares = draft({ mode: 'shares', included: ['alex', 'ben', 'claire'], shares: { alex: 2, claire: 0, emma: 5 } })
    expect(buildSplit(shares, six)).toEqual({ mode: 'shares', shares: { alex: 2, ben: 1, claire: 0 } })
  })

  it('percent: emits only populated included basis points', () => {
    const percent = draft({
      mode: 'percent',
      included: ['alex', 'ben', 'claire'],
      basisPoints: { alex: 6_000, ben: 0, claire: null, emma: 4_000 },
    })
    expect(buildSplit(percent, six)).toEqual({ mode: 'percent', basis_points: { alex: 6_000, ben: 0 } })
  })

  it('exact: emits only populated included amounts', () => {
    const exact = draft({ mode: 'exact', included: ['alex', 'ben'], amounts: { alex: 70, ben: 30, claire: 5 } })
    expect(buildSplit(exact, six)).toEqual({ mode: 'exact', amounts: { alex: 70, ben: 30 } })
  })
})

describe('splitProblem validation', () => {
  it('requires at least one participant', () => {
    expect(splitProblem(draft({ included: [] }), six, 100)).toEqual({ key: 'noParticipants' })
  })

  it('rejects all-zero shares', () => {
    const zero = draft({ mode: 'shares', included: ['alex'], shares: { alex: 0 } })
    expect(splitProblem(zero, six, 100)).toEqual({ key: 'sharesZero' })
  })

  it('requires percent basis points to total 10,000', () => {
    const under = draft({ mode: 'percent', included: ['alex', 'ben'], basisPoints: { alex: 5_000, ben: 4_999 } })
    expect(splitProblem(under, six, 100)).toEqual({ key: 'missing', percent: 1 })
    expect(weightTotal(under, six)).toBe(9_999)
    const over = draft({ mode: 'percent', included: ['alex', 'ben'], basisPoints: { alex: 5_000, ben: 5_001 } })
    expect(splitProblem(over, six, 100)).toEqual({ key: 'excess', percent: 1 })
    const exact = draft({ mode: 'percent', included: ['alex', 'ben'], basisPoints: { alex: 5_000, ben: 5_000 } })
    expect(splitProblem(exact, six, 100)).toBeNull()
  })

  it('requires exact amounts to equal expense amount', () => {
    const short = draft({ mode: 'exact', included: ['alex', 'ben'], amounts: { alex: 70_000, ben: 22_000 } })
    expect(splitProblem(short, six, 100_000)).toEqual({ key: 'missing', amount: 8_000 })
    expect(splitProblem(short, six, 90_000)).toEqual({ key: 'excess', amount: 2_000 })
    expect(splitProblem(short, six, 92_000)).toBeNull()
    expect(splitProblem(short, six, null)).toBeNull()
  })
})
