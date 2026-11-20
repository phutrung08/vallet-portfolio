import { computed } from 'vue'
import type { TripDetail, TripSpendSummary } from '@/entities'
import { useTripSource } from '@/lib/tripSource'
import { useAsyncData } from '@/lib/useAsyncData'

/** Loads trip metadata alongside its server-computed spend summary from `GET /trips/:id/summary`. */
export function useTripSummary(tripId: () => string) {
  const { read } = useTripSource()
  const { data, status, error, reload } = useAsyncData(async (signal) => {
    const base = `/trips/${encodeURIComponent(tripId())}`
    const [trip, summary] = await Promise.all([
      read<TripDetail>(base, signal),
      read<TripSpendSummary>(`${base}/summary`, signal),
    ])
    return { trip, summary }
  })
  return {
    trip: computed(() => data.value?.trip),
    summary: computed(() => data.value?.summary),
    status,
    error,
    reload,
  }
}
