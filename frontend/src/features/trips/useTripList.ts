import { computed } from 'vue'
import type { TripSummary } from '@/entities'
import { api } from '@/lib/api'
import { useAsyncData } from '@/lib/useAsyncData'

/**
 * Fetches the device's active trips fresh on each home screen visit so newly created
 * or closed trips appear without stale store caches.
 */
export function useTripList() {
  const { data, status, error, cachedCopy, reload, refresh } = useAsyncData((signal) =>
    api.get<{ trips: TripSummary[] }>('/trips', { signal }),
  )
  const trips = computed(() => data.value?.trips ?? [])
  return { trips, status, error, cachedCopy, reload, refresh }
}
