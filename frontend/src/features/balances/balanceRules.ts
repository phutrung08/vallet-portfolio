import type { MemberStanding, Payment, Transfer, TripMember } from '@/entities'

export type MeStatus = 'receive' | 'pay' | 'settled'

export function meStatus(net: number): MeStatus {
  if (net > 0) return 'receive'
  return net < 0 ? 'pay' : 'settled'
}

/** Places transfers involving `me` first while preserving server ordering within each group. */
export function transfersMeFirst(transfers: readonly Transfer[], me: string): Transfer[] {
  const mine = (transfer: Transfer) => transfer.payer === me || transfer.payee === me
  return [...transfers.filter(mine), ...transfers.filter((transfer) => !mine(transfer))]
}

/** Orders recorded payments newest first by payment date, then creation timestamp. */
export function newestPaymentsFirst(payments: readonly Payment[]): Payment[] {
  return [...payments].sort(
    (a, b) => b.paid_on.localeCompare(a.paid_on) || b.created_at.localeCompare(a.created_at),
  )
}

/** Share of total obligation covered by upfront payments, capped at 100 for the bar. */
export function coveredPercent(fronted: number, share: number): number {
  if (share <= 0) return fronted > 0 ? 100 : 0
  return Math.min(100, Math.round((fronted / share) * 100))
}

/** Orders member standings by trip position; unknown members sort last. */
export function standingsInTripOrder(
  standings: readonly MemberStanding[],
  members: readonly TripMember[],
): MemberStanding[] {
  const position = new Map(members.map((member) => [member.id, member.position]))
  const at = (standing: MemberStanding) => position.get(standing.member_id) ?? Infinity
  return [...standings].sort((a, b) => at(a) - at(b))
}

/** Number of days within which a receiving bank-account change triggers a reminder banner. */
export const ACCOUNT_CHANGE_WARNING_DAYS = 7

export function changedRecently(changedAt: string | null, now: Date): boolean {
  if (changedAt === null) return false
  return now.getTime() - new Date(changedAt).getTime() <= ACCOUNT_CHANGE_WARNING_DAYS * 86_400_000
}
