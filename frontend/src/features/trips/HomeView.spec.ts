import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { TripSummary } from '@/entities'
import HomeView from '@/features/trips/HomeView.vue'
import { splitTestRoutes } from '@/features/trips/splitHarness'
import { ApiError, api } from '@/lib/api'
import { createAppI18n, type AppLocale } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn() },
}))

const get = vi.mocked(api.get)
const TODAY = new Date(2026, 10, 6)

function trip(overrides: Partial<TripSummary> = {}): TripSummary {
  return {
    id: 'trip-1',
    name: 'Da Lat',
    currency: 'VND',
    starts_on: '2026-11-05',
    ends_on: '2026-11-08',
    uses_fund: false,
    closed: false,
    member_count: 6,
    me: 'member-1',
    ...overrides,
  }
}

async function mountHome(locale: AppLocale = 'en', trips: TripSummary[] = []) {
  get.mockResolvedValue({ trips })
  const router = createRouter({ history: createMemoryHistory(), routes: splitTestRoutes })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(HomeView, {
    props: { now: () => TODAY },
    global: { plugins: [createAppI18n(locale), router] },
  })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  get.mockReset()
})

describe('HomeView loading and error', () => {
  it('shows a busy skeleton until the list arrives', () => {
    get.mockReturnValue(new Promise(() => {}))
    const router = createRouter({ history: createMemoryHistory(), routes: splitTestRoutes })
    const wrapper = mount(HomeView, { global: { plugins: [createAppI18n('en'), router] } })
    const busy = wrapper.get('[aria-busy="true"]')
    expect(busy.findAll('.card-ink')).toHaveLength(2)
    expect(wrapper.find('h1').exists()).toBe(false)
  })

  it('shows the mapped message and retries the request', async () => {
    get.mockRejectedValueOnce(new ApiError(0, 'network_error', 'Network error'))
    const router = createRouter({ history: createMemoryHistory(), routes: splitTestRoutes })
    const wrapper = mount(HomeView, { global: { plugins: [createAppI18n('en'), router] } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('No connection. Please try again.')

    get.mockResolvedValueOnce({ trips: [trip()] })
    const retry = wrapper.findAll('button').find((button) => button.text() === 'Try again')
    await retry?.trigger('click')
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Da Lat')
  })
})

describe('HomeView empty state', () => {
  it('shows the tagline as the only h1 in both languages', async () => {
    const enHome = await mountHome('en')
    expect(enHome.wrapper.findAll('h1')).toHaveLength(1)
    expect(enHome.wrapper.get('h1').text()).toBe('Wander together, split fair')
    const viHome = await mountHome('vi')
    expect(viHome.wrapper.get('h1').text()).toBe('Đi cùng nhau, chia sòng phẳng')
  })

  it('renders three benefit rows', async () => {
    const { wrapper } = await mountHome('en')
    expect(wrapper.findAll('ul li').map((item) => item.text())).toEqual([
      'Log expenses as you go',
      'Share a link, everyone adds',
      'See who pays whom, settle with a QR scan',
    ])
  })

  it('goes to /trips/new when the primary button is clicked', async () => {
    const { wrapper, router } = await mountHome('en')
    const button = wrapper.get('header ~ div button')
    expect(button.text()).toBe('Create a trip')
    await button.trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/new'))
  })

  it('links to the sample trip, the invite flow and settings', async () => {
    const { wrapper } = await mountHome('en')
    const links = wrapper.findAll('a')
    const byText = (text: string) => links.find((link) => link.text() === text)
    expect(byText('View a sample trip')?.attributes('href')).toBe('/demo')
    expect(byText('I have an invite link')?.attributes('href')).toBe('/join')
    expect(wrapper.get('a[aria-label="Settings"]').attributes('href')).toBe('/settings')
  })
})

describe('HomeView trip list', () => {
  const list = [
    trip({ id: 'now', name: 'Active trip' }),
    trip({ id: 'soon', name: 'Upcoming trip', starts_on: '2026-12-01', ends_on: '2026-12-03' }),
    trip({ id: 'done', name: 'Settled trip', closed: true }),
    trip({ id: 'undated', name: 'Undated trip', starts_on: null, ends_on: null, member_count: 1 }),
  ]

  it('renders a heading, one link card per trip and no empty-state content', async () => {
    const { wrapper } = await mountHome('en', list)
    expect(wrapper.get('h1').text()).toBe('Your trips')
    const hrefs = wrapper.findAll('ul a').map((link) => link.attributes('href'))
    expect(hrefs).toEqual(['/trips/now', '/trips/soon', '/trips/done', '/trips/undated'])
    expect(wrapper.text()).not.toContain('View a sample trip')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('gives each trip its status pill and card tone', async () => {
    const { wrapper } = await mountHome('en', list)
    const [now, soon, done, undated] = wrapper.findAll('ul li')
    expect(now?.text()).toContain('On the road')
    expect(now?.get('.ink-border').classes()).toContain('bg-green')
    expect(now?.get('.ink-border').classes()).toContain('shadow-hard')
    expect(soon?.text()).toContain('Upcoming')
    expect(soon?.get('.ink-border').classes()).toContain('bg-surface')
    expect(done?.text()).toContain('Settled')
    expect(done?.get('.ink-border').classes()).toContain('bg-sand')
    expect(done?.get('.ink-border').classes()).not.toContain('shadow-hard')
    expect(undated?.text()).toContain('On the road')
    expect(undated?.get('.ink-border').classes()).toContain('bg-surface')
  })

  it('keeps a trip that ended but is not closed as on the road without the green tone', async () => {
    const past = trip({ starts_on: '2026-10-01', ends_on: '2026-10-05' })
    const { wrapper } = await mountHome('en', [past])
    expect(wrapper.get('ul li').text()).toContain('On the road')
    expect(wrapper.get('.ink-border').classes()).toContain('bg-surface')
  })

  it('shows the date line, and omits dates when the trip has none', async () => {
    const { wrapper } = await mountHome('en', list)
    const lines = wrapper.findAll('ul li p').map((line) => line.text())
    expect(lines).toEqual([
      '11/5 – 11/8 · 6 people',
      '12/1 – 12/3 · 6 people',
      '11/5 – 11/8 · 6 people',
      '1 person',
    ])
  })

  it('pluralises the member count in English', async () => {
    const { wrapper } = await mountHome('en', [
      trip({ id: 'a', member_count: 1 }),
      trip({ id: 'b', member_count: 6 }),
    ])
    const lines = wrapper.findAll('ul li p').map((line) => line.text())
    expect(lines[0]).toContain('1 person')
    expect(lines[1]).toContain('6 people')
  })

  it('has a create button that goes to /trips/new', async () => {
    const { wrapper, router } = await mountHome('en', list)
    const create = wrapper.findAll('button').find((button) => button.text() === 'Create a trip')
    await create?.trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/new'))
  })
})

describe('HomeView refresh', () => {
  it('fetches the list again from the header button, keeping it on screen', async () => {
    const { wrapper } = await mountHome('en', [trip()])
    let answer: (value: { trips: TripSummary[] }) => void = () => {}
    get.mockReturnValueOnce(new Promise((resolve) => (answer = resolve)))
    await wrapper.get('button[aria-label="Refresh"]').trigger('click')
    expect(wrapper.text()).toContain('Da Lat')
    expect(wrapper.get('button[aria-label="Refresh"]').attributes('disabled')).toBeDefined()
    answer({ trips: [trip({ name: 'Hue' })] })
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Hue')
  })
})
