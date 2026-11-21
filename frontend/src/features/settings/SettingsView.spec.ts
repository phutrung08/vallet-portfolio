import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import SettingsView from '@/features/settings/SettingsView.vue'
import { I18N_KEY, createAppI18n, type AppLocale } from '@/lib/i18n'
import { THEME_STORAGE_KEY } from '@/lib/theme'
import enRaw from '@/locales/en.json?raw'
import viRaw from '@/locales/vi.json?raw'
import { routes } from '@/router'

interface Texts {
  settings: {
    title: string
    device: { title: string; body: string }
    theme: { light: string; dark: string }
  }
}
const texts: Record<AppLocale, Texts> = {
  en: JSON.parse(enRaw) as Texts,
  vi: JSON.parse(viRaw) as Texts,
}

async function mountSettings(locale: AppLocale = 'en') {
  const i18n = createAppI18n(locale)
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/settings')
  await router.isReady()
  const wrapper = mount(SettingsView, {
    global: { plugins: [i18n, router], provide: { [I18N_KEY as symbol]: i18n } },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  document.documentElement.lang = 'en'
})

describe('SettingsView', () => {
  it('shows the title, device note, version and a back link home', async () => {
    const wrapper = await mountSettings()
    expect(wrapper.get('h1').text()).toBe(texts.en.settings.title)
    expect(wrapper.text()).toContain(texts.en.settings.device.body)
    expect(wrapper.text()).toContain(import.meta.env.PACKAGE_VERSION)
    expect(wrapper.get('header a').attributes('href')).toBe('/')
  })

  it('contains no placeholder or dead links', async () => {
    const wrapper = await mountSettings()
    const hrefs = wrapper.findAll('a').map((link) => link.attributes('href'))
    expect(hrefs).toEqual(['/'])
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('switches the language at once, including <html lang>', async () => {
    const wrapper = await mountSettings('en')
    const vietnamese = wrapper.findAll('button').find((b) => b.text() === 'Tiếng Việt')
    await vietnamese?.trigger('click')
    expect(wrapper.get('h1').text()).toBe(texts.vi.settings.title)
    expect(document.documentElement.lang).toBe('vi')
    expect(vietnamese?.attributes('aria-pressed')).toBe('true')
  })

  it('applies and persists the theme choice', async () => {
    const wrapper = await mountSettings()
    const dark = wrapper.findAll('button').find((b) => b.text() === texts.en.settings.theme.dark)
    await dark?.trigger('click')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(dark?.attributes('aria-pressed')).toBe('true')
  })

  it('defaults to light mode when no theme is stored', async () => {
    const wrapper = await mountSettings()
    const pressed = wrapper.findAll('button[aria-pressed="true"]').map((b) => b.text())
    expect(pressed).toContain(texts.en.settings.theme.light)
  })

  it('starts from the stored theme', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    const wrapper = await mountSettings()
    const pressed = wrapper.findAll('button[aria-pressed="true"]').map((b) => b.text())
    expect(pressed).toContain(texts.en.settings.theme.dark)
  })

  it('still applies the theme when storage fails', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const wrapper = await mountSettings()
    const dark = wrapper.findAll('button').find((b) => b.text() === texts.en.settings.theme.dark)
    await dark?.trigger('click')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})
