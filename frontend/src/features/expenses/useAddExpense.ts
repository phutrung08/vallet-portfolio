import { useRoute, useRouter } from 'vue-router'
import { useSplit } from '@/lib/useSplit'

/**
 * Navigates to the full-screen add-expense route on compact phones, or selects `?pane=add`
 * in-place on split screens so the day list stays visible.
 */
export function useAddExpense(tripId: () => string): () => Promise<void> {
  const route = useRoute()
  const router = useRouter()
  const split = useSplit()
  return async () => {
    const base = `/trips/${tripId()}`
    if (!split.value) {
      await router.push(`${base}/expenses/new`)
      return
    }
    const query = route.path === base ? { ...route.query, pane: 'add' } : { pane: 'add' }
    await router.push({ path: base, query })
  }
}
