import { createApp } from 'vue'
import App from '@/App.vue'
import { I18N_KEY, LOCALE_STORAGE_KEY, createAppI18n, resolveLocale } from '@/lib/i18n'
import { initTheme } from '@/lib/theme'
import { initNavPlacement } from '@/lib/useNavPlacement'
import { router } from '@/router'
import '@/styles/main.css'

function readStoredLocale(): string | null {
  try {
    return localStorage.getItem(LOCALE_STORAGE_KEY)
  } catch {
    return null
  }
}

const locale = resolveLocale(readStoredLocale(), navigator.languages)
document.documentElement.lang = locale

initTheme()
initNavPlacement()

const i18n = createAppI18n(locale)
createApp(App).use(router).use(i18n).provide(I18N_KEY, i18n).mount('#app')
