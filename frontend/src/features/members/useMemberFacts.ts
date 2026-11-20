import type { Balances, BankAccount } from '@/entities'
import { api } from '@/lib/api'
import { useAsyncData } from '@/lib/useAsyncData'

/** Fetches member financial standings and masked receiving bank accounts for member detail view. */
export function useMemberFacts(tripId: () => string) {
  return useAsyncData(async (signal) => {
    const base = `/trips/${encodeURIComponent(tripId())}`
    const [balances, banks] = await Promise.all([
      api.get<Balances>(`${base}/balances`, { signal }),
      api.get<{ accounts: BankAccount[] }>(`${base}/bank-accounts`, { signal }),
    ])
    return { standings: balances.members, accounts: banks.accounts }
  })
}
