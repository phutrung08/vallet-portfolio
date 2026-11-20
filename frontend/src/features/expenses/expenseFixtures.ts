import type { Expense, TripMember } from '@/entities'

export const members: TripMember[] = [
  { id: 'a', display_name: 'Alex', position: 0, removed: false },
  { id: 'b', display_name: 'Ben', position: 1, removed: false },
  { id: 'c', display_name: 'Claire', position: 2, removed: false },
  { id: 'd', display_name: 'Former guest', position: 3, removed: true },
]

/** Builds a synthetic expense from a map of `memberId -> share amount`; total sums those shares. */
export function expense(
  amounts: Record<string, number>,
  overrides: Partial<Expense> = {},
): Expense {
  return {
    id: 'e1',
    title: 'Noodles',
    amount: Object.values(amounts).reduce((sum, value) => sum + value, 0),
    category: 'food',
    spent_on: '2026-11-05',
    paid_by: 'a',
    split_mode: 'equal',
    shares: Object.entries(amounts).map(([member_id, amount]) => ({
      member_id,
      weight: amount > 0 ? 1 : 0,
      amount,
    })),
    note: null,
    place: null,
    created_by: 'a',
    updated_by: null,
    version: 1,
    ...overrides,
  }
}
