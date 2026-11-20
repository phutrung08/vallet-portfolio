export interface DaySummary {
  date: string
  count: number
  total: number
}

export type ExpenseCategory = 'food' | 'transport' | 'lodging' | 'activity' | 'shopping' | 'other'
export type SplitMode = 'equal' | 'shares' | 'percent' | 'exact'

export interface ExpenseShare {
  member_id: string
  weight: number
  amount: number
}

export interface Expense {
  id: string
  title: string
  amount: number
  category: ExpenseCategory
  spent_on: string
  /** Member ID, or null when paid from the shared fund. */
  paid_by: string | null
  split_mode: SplitMode
  shares: ExpenseShare[]
  note: string | null
  place: string | null
  created_by: string
  updated_by: string | null
  version: number
}
