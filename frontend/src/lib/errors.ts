import { ApiError } from '@/lib/api'

const KNOWN_CODES = new Set([
  'network_error',
  'offline',
  'timeout',
  'rate_limited',
  'payload_too_large',
  'unauthenticated',
  'validation_error',
  'not_found',
  'trip_locked',
  'trip_closed',
  'csrf_rejected',
  'member_not_active',
  'member_already_joined',
  'no_fund',
  'fund_in_use',
  'name_taken',
  'trip_full',
  'member_is_fund_holder',
  'last_member',
  'invalid_split',
  'trip_limit_reached',
  'device_trip_limit_reached',
  'idempotency_conflict',
  'version_conflict',
  'currency_not_supported',
  'no_bank_account',
])

export function errorMessageKey(error: unknown): string {
  if (error instanceof ApiError && KNOWN_CODES.has(error.code)) return `errors.${error.code}`
  return 'errors.generic'
}
