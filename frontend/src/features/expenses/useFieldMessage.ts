import { useI18n } from 'vue-i18n'
import type { FieldMessage } from '@/features/expenses/expenseFormRules'
import { formatBasisPoints, formatMoney, type CurrencyCode } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

/** Formats a field error message, rendering numeric gaps as money or basis-point percent. */
export function useFieldMessage(currency: () => CurrencyCode) {
  const { t, locale } = useI18n()
  return (field: FieldMessage | undefined): string | undefined => {
    if (!field) return undefined
    const appLocale = locale.value as AppLocale
    const amount =
      field.percent === undefined
        ? formatMoney(field.amount ?? 0, currency(), appLocale)
        : formatBasisPoints(field.percent, appLocale)
    return t(`expenseForm.errors.${field.key}`, { amount })
  }
}
