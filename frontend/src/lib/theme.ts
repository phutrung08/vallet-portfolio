export const THEME_STORAGE_KEY = 'vallet.theme'
export const THEME_CHOICES = ['system', 'light', 'dark'] as const
export type ThemeChoice = (typeof THEME_CHOICES)[number]
export const DEFAULT_THEME: ThemeChoice = 'system'
/** Browser chrome colors matching brand green (light) and dark canvas (dark). */
export const THEME_COLORS = { light: '#17A865', dark: '#10201F' } as const

const DARK_QUERY = '(prefers-color-scheme: dark)'

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia(DARK_QUERY).matches
}

function updateThemeColorMeta(choice: ThemeChoice): void {
  const dark = choice === 'dark' || (choice === 'system' && systemPrefersDark())
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', dark ? THEME_COLORS.dark : THEME_COLORS.light)
}

function isThemeChoice(value: string | null): value is ThemeChoice {
  return THEME_CHOICES.some((choice) => choice === value)
}

export function readStoredTheme(): ThemeChoice {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isThemeChoice(stored) ? stored : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

/** Pin light/dark theme via ``data-theme``, or remove it to follow OS preference. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement
  if (choice === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', choice)
  updateThemeColorMeta(choice)
}

export function setTheme(choice: ThemeChoice): void {
  applyTheme(choice)
  try {
    localStorage.setItem(THEME_STORAGE_KEY, choice)
  } catch {
    // Storage may be unavailable in private browsing; preference stays in memory.
  }
}

export function initTheme(): void {
  applyTheme(readStoredTheme())
  if (typeof window.matchMedia !== 'function') return
  window.matchMedia(DARK_QUERY).addEventListener('change', () => {
    if (!document.documentElement.hasAttribute('data-theme')) updateThemeColorMeta('system')
  })
}
