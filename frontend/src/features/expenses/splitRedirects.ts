import type { NavigationGuard } from 'vue-router'
import type { Expense } from '@/entities'
import { api } from '@/lib/api'
import { SPLIT_QUERY } from '@/lib/useSplit'

/**
 * Full-screen expense forms are phone routes. On split layouts, redirect straight to the trip's
 * right pane so deep links or reloads never show an isolated narrow column.
 */
function wide(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia(SPLIT_QUERY).matches
}

export const addToPane: NavigationGuard = (to) => {
  if (!wide()) return true
  return { path: `/trips/${String(to.params.tripId)}`, query: { pane: 'add' }, replace: true }
}

/** Redirects `/expenses/:expenseId` (and `/edit`) into the split detail pane for its recorded day. */
export const openInPane: NavigationGuard = async (to) => {
  if (!wide()) return true
  const tripId = String(to.params.tripId)
  const expenseId = String(to.params.expenseId)
  try {
    const expense = await api.get<Expense>(
      `/trips/${encodeURIComponent(tripId)}/expenses/${encodeURIComponent(expenseId)}`,
    )
    const edit = to.name === 'edit-expense' ? { edit: 'yes' } : {}
    return {
      path: `/trips/${tripId}`,
      query: { day: expense.spent_on, expense: expense.id, ...edit },
      replace: true,
    }
  } catch {
    // Unknown or inaccessible expenses stay on the standalone route where retry/error UI lives.
    return true
  }
}
