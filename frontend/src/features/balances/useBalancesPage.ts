import { computed } from 'vue'
import type { Balances, BankAccount, Payment, TripDetail } from '@/entities'
import { liveRead, type Reader } from '@/lib/tripSource'
import { useAsyncData } from '@/lib/useAsyncData'

/** Fetches trip metadata, net balances, recorded payments, and bank accounts with AbortSignal. */
export function useBalancesPage(tripId: () => string, read: Reader = liveRead) {
  const { data, status, error, cachedCopy, reload, refresh } = useAsyncData(async (signal) => {
    const base = `/trips/${encodeURIComponent(tripId())}`
    const [trip, balances, paid, banks] = await Promise.all([
      read<TripDetail>(base, signal),
      read<Balances>(`${base}/balances`, signal),
      read<{ payments: Payment[] }>(`${base}/payments`, signal),
      read<{ accounts: BankAccount[] }>(`${base}/bank-accounts`, signal),
    ])
    return { trip, balances, payments: paid.payments, accounts: banks.accounts }
  })
  return {
    trip: computed(() => data.value?.trip),
    balances: computed(() => data.value?.balances),
    payments: computed(() => data.value?.payments ?? []),
    accounts: computed(() => data.value?.accounts ?? []),
    status,
    error,
    cachedCopy,
    reload,
    refresh,
  }
}
