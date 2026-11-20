import type { ExpenseCategory } from '@/entities'

/** Background token classes for each category segment in the breakdown bar and legend. */
export const categoryColors: Record<ExpenseCategory, string> = {
  food: 'bg-yellow',
  transport: 'bg-sky',
  lodging: 'bg-green',
  activity: 'bg-yellow-soft',
  shopping: 'bg-sky-soft',
  other: 'bg-muted',
}
