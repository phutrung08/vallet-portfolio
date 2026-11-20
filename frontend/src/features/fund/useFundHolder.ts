import { ref } from 'vue'
import { api } from '@/lib/api'

/** Enables, transfers, or disables (when holderId is null) the trip shared fund. */
export function useFundHolder(tripId: () => string, onChanged: () => Promise<void>) {
  const pending = ref(false)
  const error = ref<unknown>(null)

  /** Returns true when holder update succeeds and trip data finishes refreshing. */
  async function setHolder(holderId: string | null): Promise<boolean> {
    if (pending.value) return false
    pending.value = true
    error.value = null
    try {
      await api.put(`/trips/${encodeURIComponent(tripId())}/fund`, { holder_id: holderId })
      await onChanged()
      return true
    } catch (caught) {
      error.value = caught
      return false
    } finally {
      pending.value = false
    }
  }

  return { pending, error, setHolder }
}
