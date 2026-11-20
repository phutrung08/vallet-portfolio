export interface FundSummary {
  holder_id: string | null
  contributed: number
  spent: number
  remaining: number
}

export interface MemberContribution {
  member_id: string
  contributed: number
}

export interface Contribution {
  id: string
  member_id: string
  amount: number
  contributed_on: string
  created_by: string
  created_at: string
}

export interface FundDetail extends FundSummary {
  members: MemberContribution[]
  contributions: Contribution[]
}
