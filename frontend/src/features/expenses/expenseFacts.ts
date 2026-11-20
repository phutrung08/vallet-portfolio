import type { Expense, SplitMode, TripDetail, TripMember } from '@/entities'

export type PerPerson =
  | { kind: 'even'; amount: number; mode: SplitMode }
  | { kind: 'uneven'; min: number; max: number }

/** Translation key explaining why a locked or closed trip cannot be edited, or null if editable. */
export function readOnlyKeyOf(trip: TripDetail): string | null {
  if (trip.locked) return 'errors.trip_locked'
  return trip.closed ? 'errors.trip_closed' : null
}

export function activeMembers(members: readonly TripMember[]): TripMember[] {
  return members.filter((member) => !member.removed)
}

function owingIds(expense: Expense): Set<string> {
  return new Set(expense.shares.filter((share) => share.amount > 0).map((share) => share.member_id))
}

export function participantCount(expense: Expense): number {
  return owingIds(expense).size
}

/** Payer display name, or null when paid from the shared fund. */
export function payerName(expense: Expense, members: readonly TripMember[]): string | null {
  if (expense.paid_by === null) return null
  return members.find((member) => member.id === expense.paid_by)?.display_name ?? ''
}

/**
 * Treats equal splits whose indivisible remainder adds at most 1 minor unit as even, displaying
 * the base per-person amount; otherwise returns the min-max range.
 */
export function perPerson(expense: Expense): PerPerson | null {
  const amounts = expense.shares.map((share) => share.amount).filter((amount) => amount > 0)
  if (amounts.length === 0) return null
  const min = Math.min(...amounts)
  const max = Math.max(...amounts)
  const remainderOnly = expense.split_mode === 'equal' && max - min <= 1
  if (min === max || remainderOnly) return { kind: 'even', amount: min, mode: expense.split_mode }
  return { kind: 'uneven', min, max }
}

/** Active trip members who owe nothing for this expense. */
export function excludedNames(expense: Expense, members: readonly TripMember[]): string[] {
  const owing = owingIds(expense)
  return activeMembers(members)
    .filter((member) => !owing.has(member.id))
    .map((member) => member.display_name)
}

export function mapsUrl(place: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place)}`
}
