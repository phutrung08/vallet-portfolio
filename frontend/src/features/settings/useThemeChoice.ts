import { computed, ref } from 'vue'
import { readStoredTheme, setTheme, type ThemeChoice } from '@/lib/theme'

/** Reactive binding for switching and persisting the light/dark/system appearance theme. */
export function useThemeChoice() {
  const current = ref<ThemeChoice>(readStoredTheme())
  const theme = computed<ThemeChoice>({
    get: () => current.value,
    set: (next) => {
      current.value = next
      setTheme(next)
    },
  })
  return { theme }
}
