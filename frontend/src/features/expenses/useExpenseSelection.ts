import { computed, shallowRef, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Expense } from '@/entities'

/**
 * Coordinates the split detail pane's selected expense (`?expense=<id>&day=<date>`).
 * Manual row selection pushes history; automatic fallback selection replaces history.
 */
export function useExpenseSelection(active: Ref<boolean>) {
  const route = useRoute()
  const router = useRouter()
  const selectedId = computed(() => (typeof route.query.expense === 'string' ? route.query.expense : null))
  const shown = shallowRef<readonly Expense[]>([])

  async function select(expense: Expense, replace = false): Promise<void> {
    // Selecting the active expense still switches back from non-detail pane modes (Add or Stats).
    if (expense.id === selectedId.value && (replace || route.query.pane === undefined)) return
    // Automatic selection preserves active pane mode; user taps switch back to Details.
    const pane = replace ? route.query.pane : undefined
    const to = { query: { day: expense.spent_on, expense: expense.id, ...(pane ? { pane } : {}) } }
    await (replace ? router.replace(to) : router.push(to))
  }

  watch([active, shown, selectedId], () => {
    const first = shown.value[0]
    if (!active.value || !first || shown.value.some((expense) => expense.id === selectedId.value)) return
    void select(first, true)
  })

  /** Registers visible day expenses so automatic selection follows when the active row leaves the list. */
  function listShown(list: readonly Expense[]): void {
    shown.value = list
  }

  return { selectedId, select, listShown }
}
