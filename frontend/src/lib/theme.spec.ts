import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  THEME_COLORS,
  THEME_STORAGE_KEY,
  applyTheme,
  initTheme,
  readStoredTheme,
  setTheme,
} from '@/lib/theme'

const meta = () => document.head.querySelector('meta[name="theme-color"]')

function stubSystemDark(matches: boolean): () => void {
  let listener: () => void = () => {}
  const query = {
    matches,
    addEventListener: (_type: string, callback: () => void) => {
      listener = callback
    },
  }
  vi.stubGlobal('matchMedia', () => query)
  return () => {
    query.matches = !query.matches
    listener()
  }
}

beforeEach(() => {
  document.head.insertAdjacentHTML('beforeend', '<meta name="theme-color" content="#17A865">')
})

afterEach(() => {
  vi.unstubAllGlobals()
  meta()?.remove()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

describe('readStoredTheme', () => {
  it('defaults to the light theme', () => {
    expect(readStoredTheme()).toBe('light')
  })

  it.each(['light', 'dark', 'system'] as const)('returns the stored %s choice', (choice) => {
    localStorage.setItem(THEME_STORAGE_KEY, choice)
    expect(readStoredTheme()).toBe(choice)
  })

  it('ignores an unknown stored value', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'sepia')
    expect(readStoredTheme()).toBe('light')
  })

  it('falls back to the light theme when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readStoredTheme()).toBe('light')
  })
})

describe('applyTheme', () => {
  it('pins light and dark on <html> and removes the attribute for system', () => {
    const root = document.documentElement
    applyTheme('dark')
    expect(root.getAttribute('data-theme')).toBe('dark')
    applyTheme('light')
    expect(root.getAttribute('data-theme')).toBe('light')
    applyTheme('system')
    expect(root.hasAttribute('data-theme')).toBe(false)
  })
})

describe('theme-color meta', () => {
  it('matches the pinned theme', () => {
    applyTheme('dark')
    expect(meta()?.getAttribute('content')).toBe(THEME_COLORS.dark)
    applyTheme('light')
    expect(meta()?.getAttribute('content')).toBe(THEME_COLORS.light)
  })

  it('follows the system preference for the system choice', () => {
    stubSystemDark(true)
    applyTheme('system')
    expect(meta()?.getAttribute('content')).toBe(THEME_COLORS.dark)
  })

  it('uses light when matchMedia is unavailable', () => {
    applyTheme('system')
    expect(meta()?.getAttribute('content')).toBe(THEME_COLORS.light)
  })

  it('does nothing when the page has no meta tag', () => {
    meta()?.remove()
    expect(() => applyTheme('dark')).not.toThrow()
  })

  it('updates when the system preference changes while following it', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'system')
    const toggle = stubSystemDark(false)
    initTheme()
    expect(meta()?.getAttribute('content')).toBe(THEME_COLORS.light)
    toggle()
    expect(meta()?.getAttribute('content')).toBe(THEME_COLORS.dark)
  })

  it('ignores system changes while a theme is pinned', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
    const toggle = stubSystemDark(false)
    initTheme()
    toggle()
    expect(meta()?.getAttribute('content')).toBe(THEME_COLORS.light)
  })
})

describe('setTheme', () => {
  it('applies and persists the choice', () => {
    setTheme('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('still applies the choice when storage throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => setTheme('dark')).not.toThrow()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})

describe('initTheme', () => {
  it('pins the light theme by default when nothing is stored', () => {
    initTheme()
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('applies the stored choice at startup', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    initTheme()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})
