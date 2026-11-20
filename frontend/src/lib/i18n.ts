import type { InjectionKey } from 'vue'
import { createI18n } from 'vue-i18n'
import en from '@/locales/en.json'
import vi from '@/locales/vi.json'

export const SUPPORTED_LOCALES = ['en', 'vi'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]
export const DEFAULT_LOCALE: AppLocale = 'en'
export const LOCALE_STORAGE_KEY = 'vallet.locale'

type MessageSchema = typeof en

function isSupported(value: string | null | undefined): value is AppLocale {
  return SUPPORTED_LOCALES.some((locale) => locale === value)
}

export function resolveLocale(
  stored: string | null,
  navigatorLanguages: readonly string[],
): AppLocale {
  if (isSupported(stored)) return stored
  for (const language of navigatorLanguages) {
    const primary = language.split('-')[0]?.toLowerCase()
    if (isSupported(primary)) return primary
  }
  return DEFAULT_LOCALE
}

export function createAppI18n(locale: AppLocale) {
  return createI18n<[MessageSchema], AppLocale, false>({
    legacy: false,
    locale,
    fallbackLocale: DEFAULT_LOCALE,
    messages: { en, vi },
    missingWarn: import.meta.env.DEV,
    fallbackWarn: import.meta.env.DEV,
  })
}

export type AppI18n = ReturnType<typeof createAppI18n>

export const I18N_KEY: InjectionKey<AppI18n> = Symbol('app-i18n')

export function setLocale(i18n: AppI18n, locale: AppLocale): void {
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
  try {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  } catch {
    // Storage may be unavailable in private browsing; preference stays in memory.
  }
}
