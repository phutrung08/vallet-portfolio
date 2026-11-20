import { formatDayMonth } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'
import type { TripDetail, TripMember, TripSummary } from '@/entities'

export type TripPhase = 'closed' | 'upcoming' | 'ongoing'
type TripDates = Pick<TripSummary, 'starts_on' | 'ends_on'>

/** Local calendar date as YYYY-MM-DD matching API date fields for lexicographical comparison. */
export function localIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function tripPhase(trip: TripSummary, today: string): TripPhase {
  if (trip.closed) return 'closed'
  return trip.starts_on !== null && trip.starts_on > today ? 'upcoming' : 'ongoing'
}

export function includesToday(trip: TripDates, today: string): boolean {
  const { starts_on: start, ends_on: end } = trip
  if (start === null && end === null) return false
  return (start === null || start <= today) && (end === null || today <= end)
}

export function dateRangeLabel(trip: TripDates, locale: AppLocale): string {
  const { starts_on: start, ends_on: end } = trip
  const days = [start, end]
    .filter((day): day is string => day !== null)
    .map((day) => formatDayMonth(day, locale))
  return [...new Set(days)].join(' – ')
}

/** Share of the fund already spent as a whole percent capped at 100 for the progress bar. */
export function spentPercent(contributed: number, spent: number): number {
  if (spent <= 0) return 0
  if (contributed <= 0) return 100
  return Math.min(100, Math.round((spent / contributed) * 100))
}

export function activeMemberCount(trip: Pick<TripDetail, 'members'>): number {
  return activeMembers(trip).length
}

/** Members who have not left, ordered by position in the trip. */
export function activeMembers(trip: Pick<TripDetail, 'members'>): TripMember[] {
  return trip.members.filter((member) => !member.removed).sort((a, b) => a.position - b.position)
}
