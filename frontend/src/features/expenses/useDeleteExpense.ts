import type { Expense } from '@/entities'
import { api } from '@/lib/api'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

/** Confirmation wrapper for deleting an expense (`ask` opens modal, `confirm` deletes). */
export function useDeleteExpense(tripId: () => string, onDeleted: (expense: Expense) => Promise<void>) {
  return useConfirmedAction<Expense>(async (expense) => {
    const path = `/trips/${encodeURIComponent(tripId())}/expenses/${encodeURIComponent(expense.id)}`
    await api.delete<void>(path)
    await onDeleted(expense)
  })
}
