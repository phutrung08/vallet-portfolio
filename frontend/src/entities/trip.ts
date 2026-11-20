import type { CurrencyCode } from '@/lib/format'

export interface TripSummary {
  id: string
  name: string
  currency: CurrencyCode
  starts_on: string | null
  ends_on: string | null
  uses_fund: boolean
  closed: boolean
  member_count: number
  me: string
}

export interface TripMember {
  id: string
  display_name: string
  position: number
  removed: boolean
}

export interface TripDetail {
  id: string
  name: string
  currency: CurrencyCode
  starts_on: string | null
  ends_on: string | null
  fund_holder_id: string | null
  locked: boolean
  closed: boolean
  me: string
  members: TripMember[]
}

export interface ShareLink {
  token: string
  version: number
}

export interface PreviewMember {
  id: string
  display_name: string
  /** True when a device has already joined as this member. */
  joined: boolean
}

export interface JoinPreview {
  trip: {
    id: string
    name: string
    currency: CurrencyCode
    starts_on: string | null
    ends_on: string | null
    locked: boolean
    closed: boolean
  }
  members: PreviewMember[]
  /** Member ID currently bound to this device in the trip, if any. */
  me: string | null
}

export type JoinRequest =
  | { token: string; member_id: string }
  | { token: string; new_name: string }
