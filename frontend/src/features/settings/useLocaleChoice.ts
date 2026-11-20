import { computed, inject } from 'vue'
import { I18N_KEY, setLocale, type AppLocale } from '@/lib/i18n'

/** Reactive binding for switching and persisting the active UI language. */
export function useLocaleChoice() {
  const i18n = inject(I18N_KEY)
  if (!i18n) throw new Error('The app i18n instance is not provided')
  const locale = computed<AppLocale>({
    get: () => i18n.global.locale.value,
    set: (next) => setLocale(i18n, next),
  })
  return { locale }
}
