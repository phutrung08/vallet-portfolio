import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import type { EventPage, TripEvent } from '@/entities'
import ActivityView from '@/features/activity/ActivityView.vue'
import { trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { button, click } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const stub = defineComponent({ template: '<div />' })

const routes: RouteRecordRaw[] = [
  { path: '/trips/:tripId/activity', component: ActivityView },
  { path: '/trips/:tripId/members', component: stub },
]

const get = vi.mocked(api.get)
let wrapper: VueWrapper | undefined

const event = (id: string, kind: string, overrides: Partial<TripEvent> = {}): TripEvent => ({
  id,
  kind,
  actor_id: '1',
  subject_id: '2',
  created_at: '2026-11-06T09:12:00',
  ...overrides,
})

function serve(pages: Record<string, EventPage | Error>) {
  get.mockImplementation((path: string) => {
    if (path === '/trips/abc') return Promise.resolve(trip)
    const page = pages[path]
    if (page instanceof Error) return Promise.reject(page)
    return page ? Promise.resolve(page) : Promise.reject(new Error(`unexpected GET ${path}`))
  })
}

async function mountActivity(): Promise<VueWrapper> {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/trips/abc/activity')
  await router.isReady()
  wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return wrapper
}

const rows = (view: VueWrapper) => view.findAll('li')

beforeEach(() => {
  get.mockReset()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-06T21:50:00'))
})

afterEach(() => {
  vi.useRealTimers()
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('activity screen', () => {
  const sentences: [string, string][] = [
    ['bank_account_set', 'Alex updated their receiving account'],
    ['bank_account_removed', 'Alex removed their receiving account'],
    ['fund_holder_changed', 'Alex updated the shared fund holder'],
    ['fund_holder_assigned', 'Alex made Ben hold the shared fund'],
    ['fund_holder_cleared', 'Alex turned off the shared fund'],
    ['member_added', 'Alex added Ben'],
    ['member_renamed', 'Alex renamed Ben'],
    ['member_removed', 'Alex removed Ben from the trip'],
    ['member_joined', 'Alex joined through the link'],
    ['member_left', 'Alex left the trip'],
    ['share_link_rotated', 'Alex changed the invite link, the old one no longer works'],
    ['trip_locked', 'Alex locked the trip'],
    ['trip_unlocked', 'Alex unlocked the trip'],
    ['trip_closed', 'Alex closed the trip'],
    ['trip_reopened', 'Alex reopened the trip'],
    ['something_new', 'Alex updated the trip'],
  ]

  it.each(sentences)('renders %s as a sentence', async (kind, sentence) => {
    serve({ '/trips/abc/events': { events: [event('e1', kind)], next_before: null } })
    const view = await mountActivity()
    expect(rows(view)[0]?.find('p')?.text()).toBe(sentence)
  })

  it('bolds the actor with an element, never raw HTML, and shows the time and day', async () => {
    serve({
      '/trips/abc/events': {
        events: [
          event('e1', 'member_joined', { actor_id: '<b>x</b>' }),
          event('e2', 'trip_locked', { created_at: '2026-11-05T21:40:00' }),
          event('e3', 'trip_closed', { created_at: '2026-11-01T08:05:00' }),
        ],
        next_before: null,
      },
    })
    const view = await mountActivity()
    const [first, second, third] = rows(view)
    expect(first?.find('strong').text()).toBe('Someone')
    expect(first?.html()).not.toContain('<b>')
    expect(first?.text()).toContain('09:12 · today')
    expect(second?.find('strong').text()).toBe('Alex')
    expect(second?.text()).toContain('21:40 · yesterday')
    expect(third?.text()).toContain('08:05 · 11/1')
  })

  it('treats a missing actor as someone', async () => {
    serve({
      '/trips/abc/events': {
        events: [event('e1', 'member_added', { actor_id: null, subject_id: null })],
        next_before: null,
      },
    })
    const view = await mountActivity()
    expect(rows(view)[0]?.find('p')?.text()).toBe('Someone added Someone')
  })

  it('loads more events below the first page with an AbortSignal', async () => {
    serve({
      '/trips/abc/events': { events: [event('e1', 'trip_locked')], next_before: 'e1' },
      '/trips/abc/events?before=e1': { events: [event('e0', 'trip_unlocked')], next_before: null },
    })
    const view = await mountActivity()
    expect(rows(view)).toHaveLength(1)
    await click(button(view.element, 'Load more'))
    expect(get).toHaveBeenCalledWith('/trips/abc/events?before=e1', { signal: expect.any(AbortSignal) })
    expect(rows(view).map((row) => row.find('p').text())).toEqual([
      'Alex locked the trip',
      'Alex unlocked the trip',
    ])
    expect(button(view.element, 'Load more')).toBeUndefined()
  })

  it('keeps the list and offers a retry when loading more fails', async () => {
    serve({
      '/trips/abc/events': { events: [event('e1', 'trip_locked')], next_before: 'e1' },
      '/trips/abc/events?before=e1': new ApiError(0, 'network_error', 'Network error'),
    })
    const view = await mountActivity()
    await click(button(view.element, 'Load more'))
    expect(rows(view)).toHaveLength(1)
    expect(view.find('[role="alert"]').text()).toContain('No connection')
    expect(button(view.element, 'Try again')).toBeDefined()
  })

  it('says so when there is no activity', async () => {
    serve({ '/trips/abc/events': { events: [], next_before: null } })
    const view = await mountActivity()
    expect(view.text()).toContain('No activity yet.')
    expect(button(view.element, 'Load more')).toBeUndefined()
  })

  it('shows an error and retries the load', async () => {
    serve({ '/trips/abc/events': new ApiError(0, 'network_error', 'Network error') })
    const view = await mountActivity()
    expect(view.find('[role="alert"]').text()).toContain('No connection')
    serve({ '/trips/abc/events': { events: [event('e1', 'trip_locked')], next_before: null } })
    await click(button(view.element, 'Try again'))
    expect(rows(view)).toHaveLength(1)
  })
})
