import { useI18n } from 'vue-i18n'
import { formatMoney, formatSignedMoney, type CurrencyCode } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

/** Money formatter bound to the trip currency and active UI locale. */
export function useMoney(currency: () => CurrencyCode) {
  const { locale } = useI18n()
  return (minor: number) => formatMoney(minor, currency(), locale.value as AppLocale)
}

/** Signed money formatter showing explicit "+" or "-" for non-zero minor amounts. */
export function useSignedMoney(currency: () => CurrencyCode) {
  const { locale } = useI18n()
  return (minor: number) => formatSignedMoney(minor, currency(), locale.value as AppLocale)
}
