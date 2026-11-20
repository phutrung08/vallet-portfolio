import { computed } from 'vue'
import { useRoute } from 'vue-router'
import type { Expense, TripDetail } from '@/entities'
import { readOnlyKeyOf } from '@/features/expenses/expenseFacts'
import { ApiError, api } from '@/lib/api'
import { useAsyncData } from '@/lib/useAsyncData'

/** Fetches trip metadata and optionally an existing expense for full-screen detail/edit views. */
export function useExpensePage() {
  const route = useRoute()
  const tripId = String(route.params.tripId)
  const expenseId = typeof route.params.expenseId === 'string' ? route.params.expenseId : null
  const base = `/trips/${encodeURIComponent(tripId)}`
  const { data, status, error, reload } = useAsyncData(async (signal) => {
    const [trip, expense] = await Promise.all([
      api.get<TripDetail>(base, { signal }),
      expenseId === null
        ? null
        : api.get<Expense>(`${base}/expenses/${encodeURIComponent(expenseId)}`, { signal }),
    ])
    return { trip, expense }
  })
  const notFound = computed(() => error.value instanceof ApiError && error.value.code === 'not_found')
  const readOnlyKey = computed(() => (data.value ? readOnlyKeyOf(data.value.trip) : null))
  return {
    tripId,
    trip: computed(() => data.value?.trip),
    expense: computed(() => data.value?.expense ?? undefined),
    editing: expenseId !== null,
    status,
    error,
    notFound,
    readOnlyKey,
    reload,
  }
}
