import { computed } from 'vue'
import type { FundDetail, TripDetail } from '@/entities'
import { api } from '@/lib/api'
import { useAsyncData } from '@/lib/useAsyncData'

/** Fetches trip details and fund breakdown (when enabled) with abort support. */
export function useFundPage(tripId: () => string) {
  const { data, status, error, reload, refresh } = useAsyncData(async (signal) => {
    const base = `/trips/${encodeURIComponent(tripId())}`
    const trip = await api.get<TripDetail>(base, { signal })
    const fund =
      trip.fund_holder_id === null ? null : await api.get<FundDetail>(`${base}/fund`, { signal })
    return { trip, fund }
  })
  return {
    trip: computed(() => data.value?.trip),
    fund: computed(() => data.value?.fund ?? null),
    status,
    error,
    reload,
    refresh,
  }
}
