import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import type { TripDetail } from '@/entities'
import { account, balances } from '@/features/balances/balanceFixtures'
import MembersView from '@/features/members/MembersView.vue'
import { trip } from '@/features/trips/tripFixtures'
import { api } from '@/lib/api'
import { button, buttonContaining, click, dialog, typeInto } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'
import { mockSplit } from '@/lib/splitTestHelpers'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const stub = defineComponent({ template: '<div />' })

const routes: RouteRecordRaw[] = [
  { path: '/', component: stub },
  { path: '/trips/:tripId', component: stub },
  { path: '/trips/:tripId/members', component: MembersView },
  { path: '/trips/:tripId/activity', component: stub },
  { path: '/trips/:tripId/balances', component: stub },
  { path: '/trips/:tripId/expenses/new', component: stub },
  { path: '/settings', component: stub },
]

const get = vi.mocked(api.get)
const patch = vi.mocked(api.patch)
const del = vi.mocked(api.delete)
let wrapper: VueWrapper | undefined
let current: TripDetail

async function mountMembers(path = '/trips/abc/members') {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return { view: wrapper, router }
}

const memberParam = (router: { currentRoute: { value: { query: Record<string, unknown> } } }) =>
  router.currentRoute.value.query.member

beforeEach(() => {
  current = { ...trip, fund_holder_id: '2' }
  get.mockReset().mockImplementation((path: string) => {
    if (path === '/trips/abc') return Promise.resolve({ ...current })
    if (path === '/trips/abc/share-link') return Promise.resolve({ token: 'tok1', version: 1 })
    if (path === '/trips/abc/balances') return Promise.resolve(balances)
    if (path === '/trips/abc/bank-accounts') return Promise.resolve({ accounts: [account] })
    return Promise.reject(new Error(`unexpected GET ${path}`))
  })
  patch.mockReset().mockResolvedValue({})
  del.mockReset().mockResolvedValue(undefined)
  mockSplit(true)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('members on a split layout', () => {
  it('shows the invite card and link security until someone is picked', async () => {
    const { view, router } = await mountMembers()
    const pane = view.get('.split-detail')
    expect(pane.text()).toContain('Invite to the trip')
    expect(pane.text()).toContain('Link security')
    expect(view.find('.split-list').text()).not.toContain('Invite to the trip')
    expect(view.find('.split-list [aria-current]').exists()).toBe(false)
    expect(view.find('[aria-label="Rename Ben"]').exists()).toBe(false)
    expect(memberParam(router)).toBeUndefined()
  })

  it('opens a member with what they fronted, their share and their account', async () => {
    const { view, router } = await mountMembers()
    await click(buttonContaining(view.get('.split-list').element, 'Ben'))
    expect(memberParam(router)).toBe('2')
    const pane = view.get('.split-detail')
    expect(pane.get('h2').text()).toContain('Ben')
    expect(pane.text()).toContain('Fund holder')
    expect(pane.text()).toContain('₫100,000')
    expect(pane.text()).toContain('-₫100,000')
    expect(pane.text()).toContain('Not added yet')
    expect(pane.text()).not.toContain('Link security')
    expect(view.get('.split-list [aria-current="true"]').text()).toContain('Ben')
    await click(buttonContaining(view.get('.split-list').element, 'Alex'))
    expect(pane.text()).toContain('Vietcombank')
    expect(pane.text()).toContain('₫500,000')
    expect(pane.text()).toContain('+₫100,000')
    expect(pane.text()).not.toContain('Remove Alex from')
  })

  it('opens the member named in the URL, and goes back to the invite card', async () => {
    const { view, router } = await mountMembers('/trips/abc/members?member=2')
    expect(view.get('.split-detail h2').text()).toContain('Ben')
    await click(button(view.get('.split-detail').element, 'Invite and link security'))
    expect(memberParam(router)).toBeUndefined()
    expect(view.get('.split-detail').text()).toContain('Invite to the trip')
  })

  it('renames in the pane', async () => {
    const { view } = await mountMembers('/trips/abc/members?member=2')
    await click(button(view.get('.split-detail').element, 'Rename Ben'))
    const input = view.get('.split-detail input').element as HTMLInputElement
    expect(input.value).toBe('Ben')
    await typeInto(input, 'Jordan')
    view.get('.split-detail form').element.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushPromises()
    expect(patch).toHaveBeenCalledWith('/trips/abc/members/2', { display_name: 'Jordan' })
    expect(view.find('.split-detail input').exists()).toBe(false)
  })

  it('removes after confirming, then falls back to the invite card', async () => {
    const { view, router } = await mountMembers('/trips/abc/members?member=2')
    await click(button(view.get('.split-detail').element, 'Remove Ben from the trip'))
    current = {
      ...current,
      members: current.members.map((member) => (member.id === '2' ? { ...member, removed: true } : member)),
    }
    await click(button(dialog(), 'Remove'))
    expect(del).toHaveBeenCalledWith('/trips/abc/members/2')
    expect(memberParam(router)).toBeUndefined()
    expect(view.get('.split-detail').text()).toContain('Invite to the trip')
  })

  it('offers no rename or remove on a locked trip', async () => {
    current = { ...current, locked: true }
    const { view } = await mountMembers('/trips/abc/members?member=2')
    expect(view.get('.split-detail h2').text()).toContain('Ben')
    expect(button(view.get('.split-detail').element, 'Remove Ben from the trip')).toBeUndefined()
    expect(button(view.get('.split-detail').element, 'Rename Ben')).toBeUndefined()
  })
})
