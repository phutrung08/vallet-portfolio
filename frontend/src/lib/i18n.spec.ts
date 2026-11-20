import { afterEach, describe, expect, it, vi as vitest } from 'vitest'
import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  createAppI18n,
  resolveLocale,
  setLocale,
} from '@/lib/i18n'
import enRaw from '@/locales/en.json?raw'
import viRaw from '@/locales/vi.json?raw'

// Parse raw JSON because the vue-i18n plugin compiles JSON imports into AST functions.
const en: unknown = JSON.parse(enRaw)
const vi: unknown = JSON.parse(viRaw)

describe('resolveLocale', () => {
  it('defaults to English', () => {
    expect(DEFAULT_LOCALE).toBe('en')
  })

  it.each([
    ['stored valid vi', 'vi', ['en'], 'vi'],
    ['stored valid en', 'en', ['vi'], 'en'],
    ['stored invalid falls back to navigator', 'fr', ['vi-VN'], 'vi'],
    ['navigator en-US', null, ['en-US'], 'en'],
    ['navigator vi-VN', null, ['vi-VN'], 'vi'],
    ['navigator fr-FR then vi', null, ['fr-FR', 'vi'], 'vi'],
    ['nothing supported defaults to en', null, ['fr-FR', 'de'], 'en'],
    ['no navigator languages defaults to en', null, [], 'en'],
  ])('%s', (_name, stored, languages, expected) => {
    expect(resolveLocale(stored, languages)).toBe(expected)
  })
})

describe('setLocale', () => {
  afterEach(() => {
    vitest.restoreAllMocks()
    localStorage.clear()
    document.documentElement.lang = ''
  })

  it('updates the active locale, <html lang>, and localStorage', () => {
    const i18n = createAppI18n('en')
    setLocale(i18n, 'vi')
    expect(i18n.global.locale.value).toBe('vi')
    expect(i18n.global.t('nav.expenses')).toBe('Chi tiêu')
    expect(document.documentElement.lang).toBe('vi')
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('vi')
  })

  it('still switches when storage is unavailable', () => {
    vitest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const i18n = createAppI18n('en')
    expect(() => setLocale(i18n, 'vi')).not.toThrow()
    expect(document.documentElement.lang).toBe('vi')
  })
})

function keyPaths(node: unknown, prefix = ''): string[] {
  if (typeof node !== 'object' || node === null) return [prefix]
  return Object.entries(node).flatMap(([key, value]) =>
    keyPaths(value, prefix ? `${prefix}.${key}` : key),
  )
}

function leafValues(node: unknown, prefix = ''): [string, unknown][] {
  if (typeof node !== 'object' || node === null) return [[prefix, node]]
  return Object.entries(node).flatMap(([key, value]) =>
    leafValues(value, prefix ? `${prefix}.${key}` : key),
  )
}

describe('locale files', () => {
  it('have identical keys with non-empty string translations and zero placeholders', () => {
    const enKeys = keyPaths(en).sort()
    const viKeys = keyPaths(vi).sort()
    expect(enKeys).toEqual(viKeys)

    for (const [key, value] of [...leafValues(en), ...leafValues(vi)]) {
      expect(typeof value, key).toBe('string')
      expect((value as string).trim().length, key).toBeGreaterThan(0)
    }

    expect(enKeys.some((k) => k.startsWith('placeholder.'))).toBe(false)
    expect(enKeys.some((k) => k.startsWith('settings.pro.'))).toBe(false)
    expect(enKeys.some((k) => k.startsWith('settings.support.'))).toBe(false)
  })
})
