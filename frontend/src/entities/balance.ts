import type { CurrencyCode } from '@/lib/format'
import type { DaySummary, ExpenseCategory } from './expense'

export interface MemberStanding {
  member_id: string
  paid: number
  contributed: number
  share: number
  sent: number
  received: number
  /** Positive: member is owed money; negative: member owes money. */
  net: number
  removed: boolean
}

export interface Transfer {
  payer: string
  payee: string
  amount: number
}

export interface Balances {
  currency: CurrencyCode
  fund: { holder_id: string | null; remaining: number }
  members: MemberStanding[]
  transfers: Transfer[]
}

export interface Payment {
  id: string
  payer: string
  payee: string
  amount: number
  paid_on: string
  note: string | null
  created_by: string
  created_at: string
}

/** VietQR payload string paired with masked payee details for confirmation before transfer. */
export interface VietQr {
  payload: string
  bank_bin: string
  bank_short_name: string
  account_name: string
  account_last4: string
  amount: number
  message: string
}

export interface CategoryBreakdown {
  category: ExpenseCategory
  count: number
  amount: number
  /** Whole integer percentage summing to 100 across non-empty categories. */
  percent: number
}

export interface PayerBreakdown {
  paid_by: string | null
  count: number
  amount: number
}

export interface TripSpendSummary {
  currency: CurrencyCode
  total: number
  expense_count: number
  active_member_count: number
  day_count: number
  per_person: number
  per_day: number
  categories: CategoryBreakdown[]
  payers: PayerBreakdown[]
  days: DaySummary[]
}
