import type { DaySummary } from '@/entities'

const MS_PER_DAY = 86_400_000

function utcMs(isoDate: string): number {
  return Date.parse(`${isoDate}T00:00:00Z`)
}

/** 1-based trip day index, or null when the trip has no start date or the date precedes it. */
export function tripDayNumber(date: string, startsOn: string | null): number | null {
  if (startsOn === null || date < startsOn) return null
  return Math.round((utcMs(date) - utcMs(startsOn)) / MS_PER_DAY) + 1
}

/** Today if present in `days`, otherwise the newest recorded day (list arrives newest first). */
export function defaultDay(days: readonly DaySummary[], today: string): string | null {
  if (days.some((day) => day.date === today)) return today
  return days[0]?.date ?? null
}
