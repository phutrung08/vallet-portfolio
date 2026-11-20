import type { Balances, BankAccount, MemberStanding, Payment, TripDetail } from '@/entities'
import { trip } from '@/features/trips/tripFixtures'

export const standing = (memberId: string, overrides: Partial<MemberStanding> = {}): MemberStanding => ({
  member_id: memberId,
  paid: 0,
  contributed: 0,
  share: 0,
  sent: 0,
  received: 0,
  net: 0,
  removed: false,
  ...overrides,
})

/** Alex (me) is owed ₫100,000; Ben owes ₫100,000; Former guest has settled net 0. */
export const balances: Balances = {
  currency: 'VND',
  fund: { holder_id: null, remaining: 0 },
  members: [
    standing('1', { paid: 400_000, contributed: 100_000, share: 400_000, net: 100_000 }),
    standing('2', { paid: 0, share: 100_000, net: -100_000 }),
    standing('3', { paid: 0, share: 0, net: 0, removed: true }),
  ],
  transfers: [
    { payer: '2', payee: '3', amount: 30_000 },
    { payer: '2', payee: '1', amount: 70_000 },
  ],
}

export const payment: Payment = {
  id: 'p1',
  payer: '2',
  payee: '1',
  amount: 20_000,
  paid_on: '2026-11-07',
  note: null,
  created_by: '2',
  created_at: '2026-11-07T09:00:00Z',
}

export const account: BankAccount = {
  member_id: '1',
  bank_bin: '970436',
  bank_short_name: 'Vietcombank',
  account_last4: '6789',
  account_name: 'ALEX RIVERA',
  updated_at: '2026-11-07T09:00:00Z',
  bank_account_changed_at: null,
}

/** Mock GET responder for balances page requests; rejects unrecognized endpoints. */
export function serveBalances(
  tripOverrides: Partial<TripDetail> = {},
  balancesOut: Balances = balances,
  payments: Payment[] = [],
  accounts: BankAccount[] = [],
) {
  return (path: string): Promise<unknown> => {
    if (path === '/trips/abc') return Promise.resolve({ ...trip, ...tripOverrides })
    if (path === '/trips/abc/balances') return Promise.resolve(balancesOut)
    if (path === '/trips/abc/payments') return Promise.resolve({ payments })
    if (path === '/trips/abc/bank-accounts') return Promise.resolve({ accounts })
    return Promise.reject(new Error(`unexpected GET ${path}`))
  }
}
