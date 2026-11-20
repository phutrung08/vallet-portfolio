import { describe, expect, it } from 'vitest'
import type { Payment, Transfer } from '@/entities'
import { standing } from '@/features/balances/balanceFixtures'
import {
  coveredPercent,
  meStatus,
  newestPaymentsFirst,
  standingsInTripOrder,
  transfersMeFirst,
} from '@/features/balances/balanceRules'

const transfer = (payer: string, payee: string): Transfer => ({ payer, payee, amount: 1 })

describe('meStatus', () => {
  it.each([
    [10, 'receive'],
    [-10, 'pay'],
    [0, 'settled'],
  ] as const)('maps net %i -> %s', (net, status) => {
    expect(meStatus(net)).toBe(status)
  })
})

describe('transfersMeFirst', () => {
  it('places transfers involving current user first while keeping relative order', () => {
    const all = [transfer('2', '3'), transfer('1', '2'), transfer('3', '4'), transfer('4', '1')]
    expect(transfersMeFirst(all, '1')).toEqual([
      transfer('1', '2'),
      transfer('4', '1'),
      transfer('2', '3'),
      transfer('3', '4'),
    ])
  })

  it('does not mutate input array', () => {
    const all = [transfer('2', '3'), transfer('1', '2')]
    transfersMeFirst(all, '1')
    expect(all[0]).toEqual(transfer('2', '3'))
  })
})

describe('newestPaymentsFirst', () => {
  const payment = (id: string, paidOn: string, createdAt: string): Payment => ({
    id,
    payer: '1',
    payee: '2',
    amount: 1,
    paid_on: paidOn,
    note: null,
    created_by: '1',
    created_at: createdAt,
  })

  it('sorts descending by paid_on then created_at', () => {
    const sorted = newestPaymentsFirst([
      payment('a', '2026-11-05', '2026-11-05T09:00:00Z'),
      payment('b', '2026-11-06', '2026-11-06T08:00:00Z'),
      payment('c', '2026-11-06', '2026-11-06T10:00:00Z'),
    ])
    expect(sorted.map((item) => item.id)).toEqual(['c', 'b', 'a'])
  })
})

describe('coveredPercent', () => {
  it.each([
    [0, 100, 0],
    [50, 100, 50],
    [1, 3, 33],
    [250, 100, 100],
    [0, 0, 0],
    [10, 0, 100],
  ])('covers %i of share %i as %i%%', (fronted, share, percent) => {
    expect(coveredPercent(fronted, share)).toBe(percent)
  })
})

describe('standingsInTripOrder', () => {
  it('orders standings by member position with unknowns last', () => {
    const members = [
      { id: 'b', display_name: 'B', position: 0, removed: false },
      { id: 'a', display_name: 'A', position: 1, removed: false },
    ]
    const sorted = standingsInTripOrder([standing('x'), standing('a'), standing('b')], members)
    expect(sorted.map((item) => item.member_id)).toEqual(['b', 'a', 'x'])
  })
})
