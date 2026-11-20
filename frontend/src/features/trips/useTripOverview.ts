import { computed } from 'vue'
import type { Balances, DaySummary, Expense, MemberStanding } from '@/entities'
import { liveRead } from '@/lib/tripSource'
import { useAsyncData } from '@/lib/useAsyncData'

const RECENT_COUNT = 4

/**
 * Fetches overview metrics for a trip selected on the split home screen:
 * total spent, current user standing, and up to four most recent expenses.
 */
export function useTripOverview(tripId: () => string, me: () => string) {
  const { data, status, error, cachedCopy, reload } = useAsyncData(async (signal) => {
    const base = `/trips/${encodeURIComponent(tripId())}`
    const [days, balances] = await Promise.all([
      liveRead<{ days: DaySummary[] }>(`${base}/expenses/days`, signal),
      liveRead<Balances>(`${base}/balances`, signal),
    ])
    const latest = days.days[0]
    const listed = latest
      ? await liveRead<{ expenses: Expense[] }>(`${base}/expenses?day=${encodeURIComponent(latest.date)}`, signal)
      : { expenses: [] }
    return { days: days.days, balances, recent: listed.expenses.slice(0, RECENT_COUNT) }
  })
  const spentTotal = computed(() => (data.value?.days ?? []).reduce((sum, day) => sum + day.total, 0))
  const mine = computed<MemberStanding | null>(
    () => data.value?.balances.members.find((member) => member.member_id === me()) ?? null,
  )
  const recent = computed<Expense[]>(() => data.value?.recent ?? [])
  return { spentTotal, mine, recent, status, error, cachedCopy, reload }
}
