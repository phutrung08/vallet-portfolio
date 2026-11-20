import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

/** Accessible labels for the bottom/rail navigation destinations. */
export function useNavLabels() {
  const { t } = useI18n()
  return computed(() => ({
    expenses: t('nav.expenses'),
    balances: t('nav.balances'),
    add: t('nav.add'),
    members: t('nav.members'),
    settings: t('nav.settings'),
  }))
}
