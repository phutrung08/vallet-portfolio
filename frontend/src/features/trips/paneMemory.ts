import type { NavigationGuard } from 'vue-router'
import { SPLIT_QUERY } from '@/lib/useSplit'

const KEY = 'vallet.pane'

/** Right-pane mode persisted across visits; Add is transient and excluded. */
export type RememberedPane = 'details' | 'stats'

export function readRememberedPane(): RememberedPane {
  try {
    return localStorage.getItem(KEY) === 'stats' ? 'stats' : 'details'
  } catch {
    return 'details'
  }
}

export function rememberPane(mode: RememberedPane): void {
  try {
    localStorage.setItem(KEY, mode)
  } catch {
    // Storage can be unavailable (private mode); the preference is simply not persisted.
  }
}

/**
 * Redirects split-screen trip entry without `?pane=` directly to Stats when that was last active
 * so History Back does not bounce and automatic expense selection cannot race.
 */
export const restoreRememberedPane: NavigationGuard = (to) => {
  const wide = typeof window.matchMedia === 'function' && window.matchMedia(SPLIT_QUERY).matches
  if (!wide || to.query.pane !== undefined || readRememberedPane() !== 'stats') return true
  return { ...to, query: { ...to.query, pane: 'stats' }, replace: true }
}
