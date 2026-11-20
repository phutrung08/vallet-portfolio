import { computed, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Transfer } from '@/entities'
import { transfersMeFirst } from '@/features/balances/balanceRules'

/** Composite URL key identifying a unique suggested transfer pair (`payer.payee`). */
export const transferKey = (transfer: Transfer) => `${transfer.payer}.${transfer.payee}`

/**
 * Coordinates `?transfer=<payer>.<payee>` for the split balances detail pane.
 * Manual taps push history; automatic initial/fallback selection replaces history.
 */
export function useTransferSelection(
  active: Ref<boolean>,
  transfers: () => readonly Transfer[],
  me: () => string,
) {
  const route = useRoute()
  const router = useRouter()
  const selectedKey = computed(() => (typeof route.query.transfer === 'string' ? route.query.transfer : null))
  const selected = computed(() => transfers().find((item) => transferKey(item) === selectedKey.value) ?? null)

  async function select(transfer: Transfer): Promise<void> {
    if (transferKey(transfer) === selectedKey.value) return
    await router.push({ query: { ...route.query, transfer: transferKey(transfer) } })
  }

  // Advances automatically to the next transfer once the open transfer settles away.
  watch(
    [active, () => transfers(), selectedKey],
    () => {
      const first = transfersMeFirst(transfers(), me())[0]
      if (!active.value || !first || selected.value) return
      void router.replace({ query: { ...route.query, transfer: transferKey(first) } })
    },
    { immediate: true },
  )

  return { selected, selectedKey, select }
}
