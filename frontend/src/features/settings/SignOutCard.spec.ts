import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import SettingsView from '@/features/settings/SettingsView.vue'
import { dialog } from '@/lib/domTestHelpers'
import { I18N_KEY, createAppI18n, type AppLocale } from '@/lib/i18n'
import enRaw from '@/locales/en.json?raw'
import viRaw from '@/locales/vi.json?raw'
import { routes } from '@/router'

// vue-i18n compiles JSON modules at build time, so expected raw copy comes from the source JSON.
interface Texts {
  settings: {
    signOut: {
      title: string
      body: string
      button: string
      confirm: { title: string; body: string; bodyNoCount: string; stay: string; confirm: string }
    }
  }
  errors: { network_error: string }
}
const texts: Record<AppLocale, Texts> = {
  en: JSON.parse(enRaw) as Texts,
  vi: JSON.parse(viRaw) as Texts,
}

const TRIPS = { trips: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] }

function stubFetch(options: { trips?: unknown; signOut?: () => Promise<Response> } = {}) {
  const signOut = options.signOut ?? (() => Promise.resolve(new Response(null, { status: 204 })))
  const fetchMock = vi.fn((url: string) =>
    url.endsWith('/devices/me/sign-out')
      ? signOut()
      : Promise.resolve(new Response(JSON.stringify(options.trips ?? TRIPS), { status: 200 })),
  )
  vi.stubGlobal('fetch', fetchMock)
  const signOutCalls = () =>
    fetchMock.mock.calls.filter(([url]) => url.endsWith('/devices/me/sign-out'))
  return { signOutCalls }
}

function stubCaches() {
  const remove = vi.fn(() => Promise.resolve(true))
  vi.stubGlobal('caches', { delete: remove })
  return remove
}

let wrapper: VueWrapper | undefined

async function mountSettings(locale: AppLocale = 'en') {
  const i18n = createAppI18n(locale)
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/settings')
  await router.isReady()
  wrapper = mount(SettingsView, {
    attachTo: document.body,
    global: { plugins: [i18n, router], provide: { [I18N_KEY as symbol]: i18n } },
  })
  await flushPromises()
  return { router }
}

const signOutButton = (locale: AppLocale = 'en') =>
  wrapper?.findAll('button').find((b) => b.text() === texts[locale].settings.signOut.button)

function sheetButton(label: string): HTMLButtonElement {
  const found = [...(dialog()?.querySelectorAll('button') ?? [])].find(
    (b) => b.textContent.trim() === label,
  )
  if (!found) throw new Error(`No sheet button "${label}"`)
  return found
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.documentElement.lang = 'en'
})

describe('SignOutCard', () => {
  it.each(['en', 'vi'] as const)('renders the card at the end of settings in %s', async (locale) => {
    stubFetch()
    await mountSettings(locale)
    const copy = texts[locale].settings.signOut
    const card = wrapper?.findAll('section').at(-1)
    expect(card?.get('h2').text()).toBe(copy.title)
    expect(card?.text()).toContain(copy.body)
    expect(signOutButton(locale)?.classes()).toContain('text-danger')
  })

  it('shows the trip count in the confirmation', async () => {
    stubFetch()
    await mountSettings('en')
    await signOutButton('en')?.trigger('click')
    await flushPromises()
    expect(dialog()?.textContent).toContain(texts.en.settings.signOut.confirm.title)
    expect(dialog()?.textContent).toContain('open your 3 trips again.')
  })

  it('pluralizes the English count for 1 trip', async () => {
    stubFetch({ trips: { trips: [{ id: 'a' }] } })
    await mountSettings('en')
    await signOutButton('en')?.trigger('click')
    await flushPromises()
    expect(dialog()?.textContent).toContain('open your 1 trip again.')
  })

  it('uses the count-free text when there are no trips', async () => {
    stubFetch({ trips: { trips: [] } })
    await mountSettings('en')
    await signOutButton('en')?.trigger('click')
    await flushPromises()
    expect(dialog()?.textContent).toContain(texts.en.settings.signOut.confirm.bodyNoCount)
  })

  it('does nothing when the user stays', async () => {
    const { signOutCalls } = stubFetch()
    const remove = stubCaches()
    const { router } = await mountSettings('en')
    await signOutButton('en')?.trigger('click')
    await flushPromises()
    sheetButton(texts.en.settings.signOut.confirm.stay).click()
    await flushPromises()
    expect(signOutCalls()).toHaveLength(0)
    expect(remove).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/settings')
  })

  it('signs out, clears the offline copy and goes home on confirm', async () => {
    const { signOutCalls } = stubFetch()
    const remove = stubCaches()
    const { router } = await mountSettings('en')
    await signOutButton('en')?.trigger('click')
    await flushPromises()
    sheetButton(texts.en.settings.signOut.confirm.confirm).click()
    await flushPromises()
    expect(signOutCalls()).toHaveLength(1)
    const [url, init] = signOutCalls()[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/devices/me/sign-out')
    expect(init.method).toBe('POST')
    expect(remove).toHaveBeenCalledWith('vallet-api-v1')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('shows an error and stays signed in when the request fails', async () => {
    stubFetch({ signOut: () => Promise.reject(new TypeError('Failed to fetch')) })
    const remove = stubCaches()
    const { router } = await mountSettings('en')
    await signOutButton('en')?.trigger('click')
    await flushPromises()
    sheetButton(texts.en.settings.signOut.confirm.confirm).click()
    await flushPromises()
    expect(dialog()?.querySelector('[role="alert"]')?.textContent).toContain(
      texts.en.errors.network_error,
    )
    expect(remove).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/settings')
  })

  it('disables the sheet buttons while the request is pending', async () => {
    let finish: (response: Response) => void = () => undefined
    stubFetch({ signOut: () => new Promise<Response>((resolve) => (finish = resolve)) })
    stubCaches()
    await mountSettings('en')
    await signOutButton('en')?.trigger('click')
    await flushPromises()
    sheetButton(texts.en.settings.signOut.confirm.confirm).click()
    await flushPromises()
    expect(sheetButton(texts.en.settings.signOut.confirm.confirm).disabled).toBe(true)
    expect(sheetButton(texts.en.settings.signOut.confirm.stay).disabled).toBe(true)
    finish(new Response(null, { status: 204 }))
    await flushPromises()
  })
})
