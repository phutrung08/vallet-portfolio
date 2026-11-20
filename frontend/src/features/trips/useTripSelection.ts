import { computed, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TripSummary } from '@/entities'

/**
 * Tracks the trip currently shown in the home overview pane via `?trip=<id>`.
 * Selecting another trip pushes history; auto-selecting the first trip replaces history.
 */
export function useTripSelection(active: Ref<boolean>, trips: () => readonly TripSummary[]) {
  const route = useRoute()
  const router = useRouter()
  const selectedId = computed(() => (typeof route.query.trip === 'string' ? route.query.trip : null))
  const selected = computed(() => trips().find((trip) => trip.id === selectedId.value) ?? null)

  async function select(trip: TripSummary): Promise<void> {
    if (trip.id !== selectedId.value) await router.push({ query: { trip: trip.id } })
  }

  watch(
    [active, () => trips(), selectedId],
    () => {
      const first = trips()[0]
      if (active.value && first && !selected.value) void router.replace({ query: { trip: first.id } })
    },
    { immediate: true },
  )

  return { selected, select }
}
