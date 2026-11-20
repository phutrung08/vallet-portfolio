import type { Contribution, FundDetail, TripDetail, TripMember } from '@/entities'
import { activeMembers } from '@/features/trips/tripMeta'

export interface MemberTotal {
  member: TripMember
  contributed: number
}

/** Active trip members in position order with total contributed (0 if none yet). */
export function memberTotals(trip: Pick<TripDetail, 'members'>, fund: Pick<FundDetail, 'members'>): MemberTotal[] {
  const paid = new Map(fund.members.map((entry) => [entry.member_id, entry.contributed]))
  return activeMembers(trip).map((member) => ({ member, contributed: paid.get(member.id) ?? 0 }))
}

/** Orders contributions newest first by contribution date, then creation timestamp. */
export function newestFirst(contributions: readonly Contribution[]): Contribution[] {
  return [...contributions].sort(
    (a, b) =>
      b.contributed_on.localeCompare(a.contributed_on) || b.created_at.localeCompare(a.created_at),
  )
}

/** Fund can only be turned off while zero contributions and zero fund expenses exist. */
export function canTurnOff(fund: Pick<FundDetail, 'contributions' | 'spent'>): boolean {
  return fund.contributions.length === 0 && fund.spent === 0
}

/** Translation key explaining why fund writes are disabled, or null when open. */
export function readOnlyReason(trip: Pick<TripDetail, 'locked' | 'closed'>): string | null {
  if (trip.locked) return 'errors.trip_locked'
  return trip.closed ? 'errors.trip_closed' : null
}

export function contributionBody(memberId: string, amount: number, contributedOn: string) {
  return { member_id: memberId, amount, contributed_on: contributedOn }
}
