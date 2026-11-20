export interface Bank {
  bin: string
  code: string
  short_name: string
}

/** Masked view of a stored bank account; full account numbers are never returned in lists. */
export interface BankAccount {
  member_id: string
  bank_bin: string
  bank_short_name: string
  account_last4: string
  account_name: string
  updated_at: string
  /** Timestamp of the latest account change event, or null when unavailable. */
  bank_account_changed_at: string | null
}
