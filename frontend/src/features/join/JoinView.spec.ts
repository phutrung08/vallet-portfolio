import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import type { JoinPreview } from '@/entities'
import JoinView from '@/features/join/JoinView.vue'
import { ApiError, api } from '@/lib/api'
import { button, click } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn() },
}))

const stub = defineComponent({ template: '<div />' })

const routes: RouteRecordRaw[] = [
  { path: '/', component: stub },
  { path: '/trips/:tripId', component: stub },
  { path: '/join', component: JoinView },
]

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
let wrapper: VueWrapper | undefined

const TOKEN = 'Ab3_-xyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
const preview: JoinPreview = {
  trip: {
    id: 't1',
    name: 'Da Lat',
    currency: 'VND',
    starts_on: '2026-11-05',
    ends_on: '2026-11-08',
    locked: false,
    closed: false,
  },
  members: [
    { id: 'a', display_name: 'Alex', joined: true },
    { id: 'b', display_name: 'Ben', joined: false },
  ],
  me: null,
}

function servePreview(overrides: Partial<JoinPreview> = {}) {
  post.mockImplementation((path: string) => {
    if (path === '/join/preview') return Promise.resolve({ ...preview, ...overrides })
    if (path === '/join') return Promise.resolve({ id: 't1' })
    return Promise.reject(new Error(`unexpected POST ${path}`))
  })
}

async function mountJoin(hash = `#${TOKEN}`) {
  window.location.hash = hash
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/join')
  await router.isReady()
  wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return { view: wrapper, router }
}

const submit = async (view: VueWrapper) => {
  await view.get('form').trigger('submit')
  await flushPromises()
}
const choose = (view: VueWrapper, name: string) =>
  click([...view.element.querySelectorAll('li button')].find((item) => item.textContent?.includes(name)))

beforeEach(() => {
  get.mockReset().mockReturnValue(new Promise(() => {}))
  post.mockReset()
  servePreview()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
  history.replaceState(null, '', '/')
  vi.restoreAllMocks()
})

describe('JoinView token handling', () => {
  it('reads the token from the fragment, removes it from the address bar and posts it', async () => {
    // Allow jsdom's hashchange dispatch to finish before spying on replaceState.
    window.location.hash = `#${TOKEN}`
    await new Promise((resolve) => setTimeout(resolve, 20))
    const replaceState = vi.spyOn(history, 'replaceState')
    await mountJoin()
    const urls = replaceState.mock.calls.map((call) => String(call[2]))
    expect(urls.length).toBeGreaterThan(0)
    expect(urls.some((url) => url.includes('#') || url.includes(TOKEN))).toBe(false)
    expect(location.hash).toBe('')
    expect(post).toHaveBeenCalledWith(
      '/join/preview',
      { token: TOKEN },
      { signal: expect.any(AbortSignal) },
    )
  })

  it('asks for the link when there is no fragment, and takes a full link', async () => {
    const { view } = await mountJoin('')
    expect(post).not.toHaveBeenCalled()
    expect(view.get('h1').text()).toBe('Paste the invite link')
    await view.get('input').setValue(`https://vallet.example/join#${TOKEN}`)
    await submit(view)
    expect(post).toHaveBeenCalledWith(
      '/join/preview',
      { token: TOKEN },
      { signal: expect.any(AbortSignal) },
    )
    expect(view.text()).toContain("You're invited to the trip")
  })

  it('accepts a bare token and rejects a link with no token', async () => {
    const { view } = await mountJoin('')
    await view.get('input').setValue('https://vallet.example/join')
    await submit(view)
    expect(view.get('[role="alert"]').text()).toContain("That link isn't right")
    expect(post).not.toHaveBeenCalled()
    await view.get('input').setValue(TOKEN)
    await submit(view)
    expect(post).toHaveBeenCalledWith(
      '/join/preview',
      { token: TOKEN },
      { signal: expect.any(AbortSignal) },
    )
  })

  it('treats an unusable fragment as a dead link', async () => {
    const { view } = await mountJoin('#not a token')
    expect(view.text()).toContain('This link no longer works')
    expect(post).not.toHaveBeenCalled()
  })

  it('reads a second invite link opened while the screen is shown', async () => {
    servePreview()
    const { router } = await mountJoin()
    const other = 'Zz9_-xyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    window.location.hash = `#${other}`
    await router.push(`/join#${other}`)
    await flushPromises()
    expect(post).toHaveBeenLastCalledWith(
      '/join/preview',
      { token: other },
      { signal: expect.any(AbortSignal) },
    )
    expect(window.location.hash).toBe('')
  })
})

describe('JoinView picker', () => {
  it('shows the trip, the members and who is already in', async () => {
    const { view } = await mountJoin()
    expect(view.get('h1').text()).toBe('Da Lat')
    expect(view.text()).toContain("You're invited to the trip")
    expect(view.text()).toContain('2 people')
    expect(view.text()).toContain('Who are you?')
    const rows = view.findAll('li button')
    expect(rows[0]?.text()).toContain('Alex')
    expect(rows[0]?.text()).toContain('already in')
    expect(rows[1]?.text()).not.toContain('already in')
    expect(view.text()).toContain('No sign-up needed. Pick your name and go.')
    expect(button(view.element, 'Join the trip')?.disabled).toBe(true)
  })

  it('joins as an existing member, even one marked as already in', async () => {
    const { view, router } = await mountJoin()
    await choose(view, 'Alex')
    expect(view.get('[aria-pressed="true"]').text()).toContain('Alex')
    await submit(view)
    expect(post).toHaveBeenLastCalledWith('/join', { token: TOKEN, member_id: 'a' })
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/t1'))
  })

  it('joins as a new person with a normalised name', async () => {
    const { view, router } = await mountJoin()
    await choose(view, 'Alex')
    await click(button(view.element, 'New person'))
    expect(view.find('[aria-pressed="true"]').text()).toContain('New person')
    await view.get('form input').setValue('  Jordan   Lee ')
    await submit(view)
    expect(post).toHaveBeenLastCalledWith('/join', { token: TOKEN, new_name: 'Jordan Lee' })
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/t1'))
  })

  it('checks a new name before calling the server', async () => {
    const { view } = await mountJoin()
    await click(button(view.element, 'New person'))
    await submit(view)
    expect(view.get('form [role="alert"]').text()).toBe('Enter a name')
    await view.get('form input').setValue('ben')
    await submit(view)
    expect(view.get('form [role="alert"]').text()).toBe('Someone already has this name')
    expect(post).toHaveBeenCalledTimes(1)
  })

  it('offers to open the trip when this device already joined', async () => {
    servePreview({ me: 'a' })
    const { view, router } = await mountJoin()
    expect(view.text()).toContain("You're already in this trip.")
    expect(view.find('form').exists()).toBe(false)
    await click(button(view.element, 'Open the trip'))
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/t1'))
    expect(post).toHaveBeenCalledTimes(1)
  })

  it('does not let anyone join a locked trip', async () => {
    servePreview({ trip: { ...preview.trip, locked: true } })
    const { view } = await mountJoin()
    await choose(view, 'Ben')
    expect(view.get('[role="alert"]').text()).toContain('The trip is locked')
    expect(button(view.element, 'Join the trip')?.disabled).toBe(true)
  })
})

describe('JoinView errors', () => {
  it('explains a dead link on preview and links home', async () => {
    post.mockRejectedValue(new ApiError(404, 'not_found', 'x'))
    const { view } = await mountJoin()
    expect(view.text()).toContain('This link no longer works')
    expect(view.get('a').attributes('href')).toBe('/')
  })

  it('offers a retry after a network failure', async () => {
    post.mockRejectedValueOnce(new ApiError(0, 'network_error', 'x'))
    const { view } = await mountJoin()
    expect(view.get('[role="alert"]').text()).toContain('No connection')
    await click(button(view.element, 'Try again'))
    expect(view.text()).toContain('Who are you?')
  })

  it.each([
    [403, 'trip_locked', 'This trip is locked, so it is view-only.'],
    [409, 'name_taken', 'Someone in the trip already has this name.'],
    [409, 'trip_full', 'The trip is full.'],
    [429, 'rate_limited', 'Slow down a little, then try again.'],
  ])('maps %i %s when joining', async (status, code, message) => {
    const { view, router } = await mountJoin()
    post.mockRejectedValueOnce(new ApiError(status, code, 'x'))
    await choose(view, 'Ben')
    await submit(view)
    expect(view.get('form [role="alert"]').text()).toContain(message)
    expect(router.currentRoute.value.path).toBe('/join')
  })

  it('shows the dead-link screen when the link dies before joining', async () => {
    const { view } = await mountJoin()
    post.mockRejectedValueOnce(new ApiError(404, 'not_found', 'x'))
    await choose(view, 'Ben')
    await submit(view)
    expect(view.text()).toContain('This link no longer works')
  })
})
