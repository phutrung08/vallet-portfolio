import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import type { TripDetail } from '@/entities'
import ActivityView from '@/features/activity/ActivityView.vue'
import MembersView from '@/features/members/MembersView.vue'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { button, click, dialog, submitSheet, typeInto } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const stub = defineComponent({ template: '<div />' })

const routes: RouteRecordRaw[] = [
  { path: '/', component: stub },
  { path: '/trips/:tripId', component: stub },
  { path: '/trips/:tripId/members', name: 'members', component: MembersView },
  { path: '/trips/:tripId/activity', name: 'activity', component: ActivityView },
  { path: '/trips/:tripId/balances', component: stub },
  { path: '/trips/:tripId/expenses/new', component: stub },
  { path: '/settings', component: stub },
]

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
const patch = vi.mocked(api.patch)
const del = vi.mocked(api.delete)
let wrapper: VueWrapper | undefined
let current: TripDetail
let token: string
const writeText = vi.fn()

const linkOf = (value: string) => `${location.origin}/join#${value}`

function setShare(share: unknown) {
  Object.defineProperty(navigator, 'share', { value: share, configurable: true })
}

async function mountMembers() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/trips/abc/members')
  await router.isReady()
  wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return { view: wrapper, router }
}

beforeEach(() => {
  current = { ...trip, fund_holder_id: '2' }
  token = 'tok1'
  get.mockReset().mockImplementation((path: string) => {
    if (path === '/trips/abc') return Promise.resolve({ ...current })
    if (path === '/trips/abc/share-link') return Promise.resolve({ token, version: 1 })
    if (path === '/trips') return Promise.resolve({ trips: [] })
    return Promise.reject(new Error(`unexpected GET ${path}`))
  })
  post.mockReset().mockResolvedValue({})
  patch.mockReset().mockResolvedValue({})
  del.mockReset().mockResolvedValue(undefined)
  writeText.mockReset().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  setShare(undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('MembersView share card', () => {
  it('copies the link built with the token in the fragment', async () => {
    const { view } = await mountMembers()
    expect(view.text()).toContain('Anyone with the link can view and add expenses')
    expect(view.text()).toContain(linkOf('tok1'))
    await click(button(view.element, 'Copy'))
    expect(writeText).toHaveBeenCalledWith(linkOf('tok1'))
    expect(button(view.element, 'Copied')).toBeDefined()
  })

  it('tells the user when copying is not possible', async () => {
    writeText.mockRejectedValue(new Error('denied'))
    const { view } = await mountMembers()
    await click(button(view.element, 'Copy'))
    expect(view.get('[role="alert"]').text()).toContain("Couldn't copy")
  })

  it('hides Share when the browser cannot share', async () => {
    const { view } = await mountMembers()
    expect(button(view.element, 'Share')).toBeUndefined()
  })

  it('shares the link through the native sheet when available', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    setShare(share)
    const { view } = await mountMembers()
    await click(button(view.element, 'Share'))
    expect(share).toHaveBeenCalledWith(expect.objectContaining({ url: linkOf('tok1'), title: 'Da Lat' }))
  })

  it('shows the QR code of the link in a sheet', async () => {
    const { view } = await mountMembers()
    await click(button(view.element, 'QR'))
    const svg = dialog()?.querySelector('svg')
    expect(svg?.getAttribute('aria-label')).toBe('QR code of the invite link')
    expect(svg?.querySelectorAll('rect').length).toBeGreaterThan(100)
  })
})

describe('MembersView member list', () => {
  it('lists active members with You and Fund holder tags', async () => {
    const { view } = await mountMembers()
    const rows = view.findAll('main ul:not(nav ul) li')
    expect(rows.map((row) => row.text())).toEqual([
      expect.stringContaining('Alex'),
      expect.stringContaining('Ben'),
    ])
    expect(rows[0]?.text()).toContain('You')
    expect(rows[0]?.text()).not.toContain('Fund holder')
    expect(rows[1]?.text()).toContain('Fund holder')
    expect(view.text()).not.toContain('Former guest')
    expect(view.find('[aria-label="Remove Alex from the trip"]').exists()).toBe(false)
  })

  it('adds a person', async () => {
    const { view } = await mountMembers()
    await view.get('form input').setValue('  Jordan  ')
    await view.get('form').trigger('submit')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/trips/abc/members', { display_name: 'Jordan' })
    expect(view.get<HTMLInputElement>('form input').element.value).toBe('')
  })

  it.each([
    ['name_taken', 'Someone in the trip already has this name.'],
    ['trip_full', 'The trip is full.'],
  ])('maps %s when adding', async (code, message) => {
    post.mockRejectedValueOnce(new ApiError(409, code, code))
    const { view } = await mountMembers()
    await view.get('form input').setValue('Jordan')
    await view.get('form').trigger('submit')
    await flushPromises()
    expect(view.get('form [role="alert"]').text()).toBe(message)
  })

  it('refuses a duplicate name without calling the server', async () => {
    const { view } = await mountMembers()
    await view.get('form input').setValue('ben')
    await view.get('form').trigger('submit')
    await flushPromises()
    expect(view.get('form [role="alert"]').text()).toBe('Someone already has this name')
    expect(post).not.toHaveBeenCalled()
  })

  it('renames a person and maps name_taken', async () => {
    const { view } = await mountMembers()
    await click(view.get('[aria-label="Rename Ben"]').element)
    const input = dialog()?.querySelector('input')
    expect(input?.value).toBe('Ben')
    patch.mockRejectedValueOnce(new ApiError(409, 'name_taken', 'x'))
    await typeInto(input, 'Jordan')
    await submitSheet()
    expect(dialog()?.textContent).toContain('Someone in the trip already has this name.')
    await submitSheet()
    expect(patch).toHaveBeenLastCalledWith('/trips/abc/members/2', { display_name: 'Jordan' })
    expect(dialog()).toBeNull()
  })

  it('removes a person after confirming', async () => {
    const { view } = await mountMembers()
    await click(view.get('[aria-label="Remove Ben from the trip"]').element)
    expect(del).not.toHaveBeenCalled()
    del.mockRejectedValueOnce(new ApiError(409, 'member_is_fund_holder', 'x'))
    await click(button(dialog(), 'Remove'))
    expect(dialog()?.textContent).toContain('This person holds the fund.')
    await click(button(dialog(), 'Remove'))
    expect(del).toHaveBeenLastCalledWith('/trips/abc/members/2')
    expect(dialog()).toBeNull()
  })

  it('maps last_member when removing', async () => {
    del.mockRejectedValueOnce(new ApiError(409, 'last_member', 'x'))
    const { view } = await mountMembers()
    await click(view.get('[aria-label="Remove Ben from the trip"]').element)
    await click(button(dialog(), 'Remove'))
    expect(dialog()?.textContent).toContain("The last person can't be removed from the trip.")
  })

  it('hides member edits and shows why when the trip is locked', async () => {
    current = { ...current, locked: true }
    const { view } = await mountMembers()
    expect(view.text()).toContain('This trip is locked')
    expect(view.find('[aria-label^="Rename"]').exists()).toBe(false)
    expect(view.find('[aria-label^="Remove"]').exists()).toBe(false)
    expect(view.find('form').exists()).toBe(false)
    expect(button(view.element, 'Unlock')).toBeDefined()
  })
})

describe('MembersView link security', () => {
  it('rotates the link and shows the new one', async () => {
    post.mockResolvedValueOnce({ token: 'tok2', version: 2 })
    const { view } = await mountMembers()
    await click(button(view.element, 'Change invite link'))
    expect(dialog()?.textContent).toContain('People who already joined keep their access')
    expect(post).not.toHaveBeenCalled()
    await click(button(dialog(), 'Change link'))
    expect(post).toHaveBeenCalledWith('/trips/abc/share-link/rotate')
    expect(view.text()).toContain(linkOf('tok2'))
    expect(view.text()).not.toContain(linkOf('tok1'))
  })

  it('locks and unlocks, updating what is offered', async () => {
    post.mockImplementation((path: string) => {
      current = { ...current, locked: path.endsWith('/lock') }
      return Promise.resolve({})
    })
    const { view } = await mountMembers()
    await click(button(view.element, 'Lock the trip'))
    expect(dialog()?.textContent).toContain('nobody can add or change anything')
    await click(button(dialog(), 'Lock'))
    expect(post).toHaveBeenLastCalledWith('/trips/abc/lock')
    expect(view.find('form').exists()).toBe(false)
    await click(button(view.element, 'Unlock'))
    await click(button(dialog(), 'Unlock'))
    expect(post).toHaveBeenLastCalledWith('/trips/abc/unlock')
    expect(view.find('form').exists()).toBe(true)
    expect(button(view.element, 'Lock the trip')).toBeDefined()
  })

  it('leaves the trip on this device, deletes its offline copy and goes home', async () => {
    const stored = ['/api/trips', '/api/trips/abc', '/api/trips/abc/balances', '/api/trips/xyz'].map(
      (path) => new Request(`${location.origin}${path}`),
    )
    const remove = vi.fn<(request: Request) => Promise<boolean>>(() => Promise.resolve(true))
    const open = vi.fn(() => Promise.resolve({ keys: () => Promise.resolve(stored), delete: remove }))
    vi.stubGlobal('caches', { open })
    const { view, router } = await mountMembers()
    await click(button(view.element, 'Leave the trip on this device'))
    await click(button(dialog(), 'Leave'))
    expect(post).toHaveBeenCalledWith('/trips/abc/leave')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/'))
    expect(remove.mock.calls.map(([request]) => new URL(request.url).pathname)).toEqual([
      '/api/trips/abc',
      '/api/trips/abc/balances',
    ])
  })

  it('shows a failed action inside its confirmation', async () => {
    post.mockRejectedValueOnce(new ApiError(0, 'network_error', 'x'))
    const { view } = await mountMembers()
    await click(button(view.element, 'Lock the trip'))
    await click(button(dialog(), 'Lock'))
    expect(dialog()?.textContent).toContain('No connection')
  })
})

describe('activity link', () => {
  it('opens the activity screen from the members screen', async () => {
    get.mockImplementation((path: string) => {
      if (path === '/trips/abc/events') return Promise.resolve({ events: [], next_before: null })
      if (path === '/trips/abc') return Promise.resolve({ ...current })
      if (path === '/trips/abc/share-link') return Promise.resolve({ token, version: 1 })
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const { view, router } = await mountMembers()
    const link = view.get('a[href="/trips/abc/activity"]')
    expect(link.text()).toBe('Activity')
    await link.trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('activity'))
    await flushPromises()
    expect(view.text()).toContain('No activity yet.')
  })
})
