import { describe, expect, it } from 'vitest'
import {
  excludedNames,
  mapsUrl,
  participantCount,
  payerName,
  perPerson,
} from '@/features/expenses/expenseFacts'
import { expense, members } from '@/features/expenses/expenseFixtures'

describe('expense facts', () => {
  it('counts participants with non-zero shares', () => {
    expect(participantCount(expense({ a: 50, b: 50, c: 0 }))).toBe(2)
  })

  it('resolves payer name or returns null for fund', () => {
    expect(payerName(expense({ a: 1 }), members)).toBe('Alex')
    expect(payerName(expense({ a: 1 }, { paid_by: null }), members)).toBeNull()
  })

  it('classifies equal shares as even with split mode metadata', () => {
    expect(perPerson(expense({ a: 50, b: 50, c: 0 }))).toEqual({
      kind: 'even',
      amount: 50,
      mode: 'equal',
    })
  })

  it('treats a 1-unit equal-split remainder as even', () => {
    expect(perPerson(expense({ a: 34, b: 33, c: 33 }))).toMatchObject({ kind: 'even', amount: 33 })
  })

  it('reports uneven splits as a min-max range', () => {
    const uneven = expense({ a: 70, b: 30, c: 0 }, { split_mode: 'exact' })
    expect(perPerson(uneven)).toEqual({ kind: 'uneven', min: 30, max: 70 })
    expect(perPerson(expense({ a: 34, b: 33 }, { split_mode: 'shares' }))).toMatchObject({
      kind: 'uneven',
    })
  })

  it('returns null per-person summary when no positive shares exist', () => {
    expect(perPerson(expense({ a: 0 }))).toBeNull()
  })

  it('lists active exempt members while ignoring removed members', () => {
    expect(excludedNames(expense({ a: 50, b: 50, c: 0 }), members)).toEqual(['Claire'])
    expect(excludedNames(expense({ a: 100 }), members)).toEqual(['Ben', 'Claire'])
  })

  it('encodes place names safely in a Google Maps search link', () => {
    expect(mapsUrl('Cafe A & B')).toBe(
      'https://www.google.com/maps/search/?api=1&query=Cafe%20A%20%26%20B',
    )
  })
})
