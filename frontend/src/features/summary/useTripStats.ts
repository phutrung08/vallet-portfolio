import type { Balances, TripDetail, TripSpendSummary } from '@/entities'
import { useTripSource } from '@/lib/tripSource'
import { useAsyncData } from '@/lib/useAsyncData'

/** Loads server-computed spend breakdown and per-member standings for the split stats pane. */
export function useTripStats(trip: () => TripDetail) {
  const { read } = useTripSource()
  return useAsyncData(async (signal) => {
    const base = `/trips/${encodeURIComponent(trip().id)}`
    const [summary, balances] = await Promise.all([
      read<TripSpendSummary>(`${base}/summary`, signal),
      read<Balances>(`${base}/balances`, signal),
    ])
    return {
      summary,
      standings: balances.members,
    }
  })
}
