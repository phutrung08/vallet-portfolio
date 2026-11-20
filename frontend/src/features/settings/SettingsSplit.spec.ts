import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import SettingsView from '@/features/settings/SettingsView.vue'
import { I18N_KEY, createAppI18n } from '@/lib/i18n'
import { mockSplit } from '@/lib/splitTestHelpers'
import enRaw from '@/locales/en.json?raw'
import { routes } from '@/router'

const settingsTexts = (JSON.parse(enRaw) as {
  settings: { sections: Record<string, string>; signOut: { button: string } }
}).settings

async function mountSettings(path = '/settings') {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  const i18n = createAppI18n('en')
  const wrapper = mount(SettingsView, {
    global: { plugins: [i18n, router], provide: { [I18N_KEY as symbol]: i18n } },
  })
  await flushPromises()
  return { wrapper, router }
}

const current = (wrapper: Awaited<ReturnType<typeof mountSettings>>['wrapper']) =>
  wrapper.findAll('.split-list [aria-current="true"]').map((row) => row.text())

afterEach(() => vi.unstubAllGlobals())

describe('SettingsView on a split screen', () => {
  it('shows only the three live sections and opens appearance by default', async () => {
    mockSplit(true)
    const { wrapper, router } = await mountSettings()
    const rows = wrapper.findAll('.split-list nav button').map((row) => row.text())
    expect(rows).toEqual([
      settingsTexts.sections.appearance,
      settingsTexts.sections.nav,
      settingsTexts.sections.account,
    ])
    expect(router.currentRoute.value.query.section).toBe('appearance')
    expect(current(wrapper)).toEqual([settingsTexts.sections.appearance])
    expect(wrapper.find('.split-detail').text()).toContain('English')
  })

  it('pushes a history entry when switching categories and renders section cards', async () => {
    mockSplit(true)
    const { wrapper, router } = await mountSettings()
    const navRow = wrapper.findAll('.split-list button').find((b) => b.text() === settingsTexts.sections.nav)
    await navRow?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.section).toBe('nav')
    expect(current(wrapper)).toEqual([settingsTexts.sections.nav])
    expect(wrapper.find('.split-detail [role="radiogroup"], .split-detail [aria-pressed]').exists()).toBe(true)

    const accountRow = wrapper.findAll('.split-list button').find((b) => b.text() === settingsTexts.sections.account)
    await accountRow?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.section).toBe('account')
    expect(wrapper.find('.split-detail').text()).toContain(settingsTexts.signOut.button)
    expect(wrapper.findAll('.split-detail a')).toHaveLength(0)

    await router.back()
    await flushPromises()
    expect(current(wrapper)).toEqual([settingsTexts.sections.nav])
  })

  it('replaces an unknown category with the first one', async () => {
    mockSplit(true)
    const { router } = await mountSettings('/settings?section=nope')
    expect(router.currentRoute.value.query.section).toBe('appearance')
  })

  it('leaves phones on the single page with the URL untouched', async () => {
    mockSplit(false)
    const { wrapper, router } = await mountSettings()
    expect(router.currentRoute.value.query.section).toBeUndefined()
    expect(wrapper.find('.split-layout').exists()).toBe(false)
    expect(wrapper.findAll('nav a')).toHaveLength(0)
  })
})
