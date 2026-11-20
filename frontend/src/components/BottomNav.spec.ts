import { afterEach, describe, expect, it } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import BottomNav from '@/components/BottomNav.vue'
import { initNavPlacement, useNavPlacement } from '@/lib/useNavPlacement'
import { tripSourceKey, type TripSource } from '@/lib/tripSource'

const labels = {
  expenses: 'Expenses',
  balances: 'Balances',
  add: 'Add expense',
  members: 'Members',
  settings: 'Settings',
}
const stub = { template: '<div />' }
let wrapper: VueWrapper | undefined

async function mountAt(path: string, source?: TripSource) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/trips/:id', component: stub },
      { path: '/trips/:id/balances', component: stub },
      { path: '/trips/:id/members', component: stub },
      { path: '/demo', component: stub },
      { path: '/demo/balances', component: stub },
      { path: '/settings', component: stub },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount(BottomNav, {
    props: { tripId: 't1', labels },
    global: {
      plugins: [router],
      provide: source ? { [tripSourceKey as symbol]: source } : {},
    },
  })
  await flushPromises()
  return wrapper
}

const { setPhone, setWide } = useNavPlacement()

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  localStorage.clear()
  initNavPlacement()
})

describe('BottomNav', () => {
  it('renders four labelled links and one action button', async () => {
    const w = await mountAt('/trips/t1')
    const links = w.findAll('a')
    expect(links.map((l) => l.attributes('href'))).toEqual([
      '/trips/t1',
      '/trips/t1/balances',
      '/trips/t1/members',
      '/settings',
    ])
    expect(links.map((l) => l.attributes('aria-label'))).toEqual([
      'Expenses',
      'Balances',
      'Members',
      'Settings',
    ])
    const buttons = w.findAll('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]?.attributes('aria-label')).toBe('Add expense')
    expect(buttons[0]?.attributes('type')).toBe('button')
  })

  it('emits add when the center button is pressed', async () => {
    const w = await mountAt('/trips/t1')
    await w.find('button').trigger('click')
    expect(w.emitted('add')).toHaveLength(1)
  })

  it.each([
    ['/trips/t1', 0],
    ['/trips/t1/balances', 1],
    ['/trips/t1/members', 2],
    ['/settings', 3],
  ])('marks only the active link at %s', async (path, activeIndex) => {
    const w = await mountAt(path)
    w.findAll('a').forEach((link, i) => {
      expect(link.attributes('aria-current')).toBe(i === activeIndex ? 'page' : undefined)
    })
  })

  it('applies active pill utility classes on icon containers', async () => {
    const w = await mountAt('/trips/t1/balances')
    const pills = w.findAll('a').map((link) => link.get('span').classes())
    pills.forEach((classes) => {
      expect(classes).toContain('rounded-pill')
      expect(classes).toContain('group-aria-[current=page]:bg-ink')
    })
    expect(w.findAll('a')[1]?.attributes('aria-current')).toBe('page')
  })

  it('shows only read-only destinations when trip source is readonly', async () => {
    const demo: TripSource = {
      read: () => Promise.reject(new Error('unused')),
      readonly: true,
      home: () => '/demo',
    }
    const w = await mountAt('/trips/t1', demo)
    expect(w.findAll('li')).toHaveLength(2)
    expect(w.findAll('a')).toHaveLength(2)
    expect(w.find('button').exists()).toBe(false)
  })

  it('exposes placement data attributes reactively for CSS', async () => {
    initNavPlacement()
    const w = await mountAt('/trips/t1')
    const nav = w.get('nav')
    expect(nav.attributes('data-phone')).toBe('bottom-center')
    expect(nav.attributes('data-wide')).toBe('rail-left')
    setPhone('edge-right')
    setWide('rail-right')
    await flushPromises()
    expect(nav.attributes('data-phone')).toBe('edge-right')
    expect(nav.attributes('data-wide')).toBe('rail-right')
  })

  it('keeps dock pill styling and rail ordering classes', async () => {
    const w = await mountAt('/trips/t1')
    expect(w.get('nav').classes()).toContain('rounded-pill')
    expect(w.get('button').element.parentElement?.classList).toContain('rail:order-first')
    expect(w.findAll('li').at(-1)?.classes()).toContain('rail:mt-auto')
  })
})
