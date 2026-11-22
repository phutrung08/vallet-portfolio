import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export interface NavLabels {
  expenses: string
  balances: string
  add: string
  members: string
  settings: string
}

/** Accessible labels for the bottom/rail navigation destinations. */
export function useNavLabels() {
  const { t } = useI18n()
  return computed<NavLabels>(() => ({
    expenses: t('nav.expenses'),
    balances: t('nav.balances'),
    add: t('nav.add'),
    members: t('nav.members'),
    settings: t('nav.settings'),
  }))
}

/** Concise visible labels shown beneath icons on the desktop vertical rail. */
export function useNavShortLabels() {
  const { t } = useI18n()
  return computed<NavLabels>(() => ({
    expenses: t('nav.short.expenses'),
    balances: t('nav.short.balances'),
    add: t('nav.short.add'),
    members: t('nav.short.members'),
    settings: t('nav.short.settings'),
  }))
}
