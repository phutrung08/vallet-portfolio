import { computed, getCurrentScope, onScopeDispose, ref } from 'vue'
import type { EventPage, TripDetail, TripEvent } from '@/entities'
import { api } from '@/lib/api'
import { useAsyncData } from '@/lib/useAsyncData'

/** Fetches trip member directory and paginated activity feed with abort-safe pagination. */
export function useActivity(tripId: () => string) {
  const events = ref<TripEvent[]>([])
  const nextBefore = ref<string | null>(null)
  const loadingMore = ref(false)
  const moreError = ref<unknown>(null)
  const base = () => `/trips/${encodeURIComponent(tripId())}`
  let moreController: AbortController | null = null

  const { data, status, error, reload } = useAsyncData(async (signal) => {
    moreController?.abort()
    moreController = null
    loadingMore.value = false
    moreError.value = null
    const [trip, page] = await Promise.all([
      api.get<TripDetail>(base(), { signal }),
      api.get<EventPage>(`${base()}/events`, { signal }),
    ])
    events.value = page.events
    nextBefore.value = page.next_before
    return trip
  })

  async function loadMore(): Promise<void> {
    if (nextBefore.value === null || loadingMore.value) return
    moreController?.abort()
    const controller = new AbortController()
    moreController = controller
    loadingMore.value = true
    moreError.value = null
    try {
      const page = await api.get<EventPage>(
        `${base()}/events?before=${encodeURIComponent(nextBefore.value)}`,
        { signal: controller.signal },
      )
      if (controller.signal.aborted) return
      events.value = [...events.value, ...page.events]
      nextBefore.value = page.next_before
    } catch (caught) {
      if (controller.signal.aborted) return
      moreError.value = caught
    } finally {
      if (moreController === controller) {
        moreController = null
        loadingMore.value = false
      }
    }
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      moreController?.abort()
      moreController = null
    })
  }

  return {
    trip: computed(() => data.value),
    events,
    hasMore: computed(() => nextBefore.value !== null),
    loadingMore,
    moreError,
    status,
    error,
    reload,
    loadMore,
  }
}
