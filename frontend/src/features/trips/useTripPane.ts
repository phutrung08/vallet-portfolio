import { computed, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { rememberPane } from '@/features/trips/paneMemory'

export type PaneMode = 'details' | 'add' | 'stats'

/**
 * Coordinates the trip screen's right pane via `?pane=`.
 * Details is default unless the trip has no expenses yet and can add one (defaulting to Add);
 * Details and Stats preferences are remembered locally across visits.
 */
export function useTripPane(canAdd: Ref<boolean>, hasExpenses: Ref<boolean>) {
  const route = useRoute()
  const router = useRouter()
  const fallback = computed<PaneMode>(() => (!hasExpenses.value && canAdd.value ? 'add' : 'details'))
  const mode = computed<PaneMode>(() => {
    const asked = route.query.pane
    if (asked === 'add') return canAdd.value ? 'add' : fallback.value
    if (asked === 'stats') return hasExpenses.value ? 'stats' : fallback.value
    return asked === 'details' ? 'details' : fallback.value
  })

  async function setMode(next: PaneMode): Promise<void> {
    if (next === mode.value) return
    const query = { ...route.query }
    if (next === fallback.value) delete query.pane
    else query.pane = next
    await router.push({ query })
  }

  watch(mode, (now) => {
    if (now !== 'add') rememberPane(now)
  })

  return { mode, setMode }
}
