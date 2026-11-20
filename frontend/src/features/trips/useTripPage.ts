import { computed } from 'vue'
import type { DaySummary, FundSummary, TripDetail } from '@/entities'
import { liveRead, type Reader } from '@/lib/tripSource'
import { useAsyncData } from '@/lib/useAsyncData'

/** Loads trip metadata, per-day expense totals, and fund summary when enabled. */
export function useTripPage(tripId: () => string, read: Reader = liveRead) {
  const { data, status, error, cachedCopy, reload, refresh } = useAsyncData(async (signal) => {
    const base = `/trips/${encodeURIComponent(tripId())}`
    const [trip, daysOut] = await Promise.all([
      read<TripDetail>(base, signal),
      read<{ days: DaySummary[] }>(`${base}/expenses/days`, signal),
    ])
    const fund = trip.fund_holder_id === null ? null : await read<FundSummary>(`${base}/fund`, signal)
    return { trip, days: daysOut.days, fund }
  })
  const trip = computed(() => data.value?.trip)
  const days = computed(() => data.value?.days ?? [])
  const fund = computed(() => data.value?.fund ?? null)
  const spentTotal = computed(() => days.value.reduce((sum, day) => sum + day.total, 0))
  return { trip, days, fund, spentTotal, status, error, cachedCopy, reload, refresh }
}
