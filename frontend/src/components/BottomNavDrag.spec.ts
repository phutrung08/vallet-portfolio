import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import BottomNav from '@/components/BottomNav.vue'
import { createAppI18n } from '@/lib/i18n'
import { HOLD_MS, SNAP_MS } from '@/lib/useNavDrag'
import { NAV_STORAGE_KEY, initNavPlacement, useNavPlacement } from '@/lib/useNavPlacement'

const labels = {
  expenses: 'Expenses',
  balances: 'Balances',
  add: 'Add expense',
  members: 'Members',
  settings: 'Settings',
}
const stub = { template: '<div />' }
const { placement } = useNavPlacement()
const capture = vi.fn()
const vibrate = vi.fn()
let wrapper: VueWrapper | undefined
let router: Router

/** Simulates viewport width (height 900) and reduced-motion preference. */
function mockScreen(width: number, reducedMotion = false) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: query.includes('reduced-motion') ? reducedMotion : width >= (query.includes('37.5rem') ? 600 : 400),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
  Object.defineProperty(document.documentElement, 'clientWidth', { value: width, configurable: true })
  Object.defineProperty(document.documentElement, 'clientHeight', { value: 900, configurable: true })
}

async function mountNav() {
  router = createRouter({
    history: createMemoryHistory(),
    routes: ['/trips/:id', '/trips/:id/balances', '/trips/:id/members', '/settings'].map((path) => ({
      path,
      component: stub,
    })),
  })
  await router.push('/trips/t1')
  await router.isReady()
  wrapper = mount(BottomNav, {
    props: { tripId: 't1', labels },
    global: { plugins: [router, createAppI18n('en')] },
    attachTo: document.body,
  })
  await flushPromises()
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  return wrapper
}

function pointer(target: Element, type: string, x: number, y: number) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, button: 0 })
  Object.defineProperties(event, { pointerId: { value: 1 }, isPrimary: { value: true } })
  target.dispatchEvent(event)
}

const nav = () => wrapper!.get('nav').element as HTMLElement
const balancesLink = () => wrapper!.findAll('a')[1]!.element
const zones = () => document.body.querySelector('[data-testid="nav-drop-zones"]')

async function hold(x = 206, y = 870, target: Element = nav()) {
  pointer(target, 'pointerdown', x, y)
  vi.advanceTimersByTime(HOLD_MS)
  await nextTick()
}

async function dragTo(x: number, y: number) {
  pointer(nav(), 'pointermove', x, y)
  await nextTick()
  pointer(nav(), 'pointerup', x, y)
  await flushPromises()
}

beforeAll(() => {
  Object.defineProperty(Element.prototype, 'setPointerCapture', { value: capture, configurable: true })
  Object.defineProperty(navigator, 'vibrate', { value: vibrate, configurable: true })
})

afterAll(() => {
  Reflect.deleteProperty(Element.prototype, 'setPointerCapture')
  Reflect.deleteProperty(navigator, 'vibrate')
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  localStorage.clear()
  initNavPlacement()
})

describe('BottomNav drag to move', () => {
  it('does nothing on small viewports below 25rem', async () => {
    mockScreen(360)
    await mountNav()
    await hold()
    expect(nav().dataset.drag).toBeUndefined()
    expect(zones()).toBeNull()
    expect(vibrate).not.toHaveBeenCalled()
    expect(wrapper!.find('[role="status"]').exists()).toBe(false)
  })

  it('lifts after the hold threshold with haptic tick and five phone drop targets', async () => {
    mockScreen(412)
    await mountNav()
    pointer(nav(), 'pointerdown', 206, 870)
    vi.advanceTimersByTime(HOLD_MS - 1)
    await nextTick()
    expect(nav().dataset.drag).toBeUndefined()
    vi.advanceTimersByTime(1)
    await nextTick()
    expect(nav().dataset.drag).toBe('dragging')
    expect(vibrate).toHaveBeenCalledWith(10)
    expect(zones()?.querySelectorAll('[data-zone]')).toHaveLength(5)
    expect(zones()?.querySelector('[data-active]')?.getAttribute('data-zone')).toBe('bottom-center')
  })

  it('treats movement beyond 8px before the hold completes as scrolling', async () => {
    mockScreen(412)
    await mountNav()
    pointer(nav(), 'pointerdown', 206, 870)
    pointer(nav(), 'pointermove', 206, 860)
    vi.advanceTimersByTime(HOLD_MS)
    await nextTick()
    expect(nav().dataset.drag).toBeUndefined()
    expect(zones()).toBeNull()
  })

  it('tolerates minor pointer jitter within slop during the hold', async () => {
    mockScreen(412)
    await mountNav()
    pointer(nav(), 'pointerdown', 206, 870)
    pointer(nav(), 'pointermove', 210, 866)
    vi.advanceTimersByTime(HOLD_MS)
    expect(nav().dataset.drag).toBe('dragging')
  })

  it('allows quick taps on links to navigate without starting drag', async () => {
    mockScreen(412)
    await mountNav()
    pointer(balancesLink(), 'pointerdown', 150, 870)
    vi.advanceTimersByTime(100)
    pointer(balancesLink(), 'pointerup', 150, 870)
    balancesLink().dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, detail: 1 }))
    await flushPromises()
    vi.advanceTimersByTime(HOLD_MS)
    expect(router.currentRoute.value.path).toBe('/trips/t1/balances')
    expect(nav().dataset.drag).toBeUndefined()
    expect(vibrate).not.toHaveBeenCalled()
  })

  it('tracks pointer translation, drops onto nearest phone zone, and swallows the trailing click', async () => {
    mockScreen(412)
    await mountNav()
    await hold(150, 870, balancesLink())
    pointer(nav(), 'pointermove', 405, 450)
    await nextTick()
    expect(nav().style.getPropertyValue('translate')).toBe('255px -420px')
    expect(capture).toHaveBeenCalledWith(1)
    expect(zones()?.querySelector('[data-active]')?.getAttribute('data-zone')).toBe('edge-right')
    pointer(nav(), 'pointerup', 405, 450)
    await flushPromises()
    expect(placement.phone).toBe('edge-right')
    expect(JSON.parse(localStorage.getItem(NAV_STORAGE_KEY) ?? '').phone).toBe('edge-right')
    expect(wrapper!.get('[role="status"]').text()).toBe('Navigation moved to the right edge')
    balancesLink().dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, detail: 1 }))
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/trips/t1')
  })

  it('drops onto the nearest rail on wide viewports', async () => {
    mockScreen(800)
    await mountNav()
    await hold(40, 300)
    expect(zones()?.querySelectorAll('[data-zone]')).toHaveLength(2)
    await dragTo(760, 500)
    expect(placement.wide).toBe('rail-right')
    expect(placement.phone).toBe('bottom-center')
  })

  it('snaps via settling state before returning to idle', async () => {
    mockScreen(412)
    await mountNav()
    await hold()
    await dragTo(20, 880)
    expect(placement.phone).toBe('bottom-left')
    expect(nav().dataset.drag).toBe('settling')
    vi.advanceTimersByTime(SNAP_MS)
    expect(nav().dataset.drag).toBeUndefined()
    expect(nav().style.getPropertyValue('translate')).toBe('')
  })

  it('finishes immediately when reduced motion is enabled', async () => {
    mockScreen(412, true)
    await mountNav()
    await hold()
    await dragTo(20, 880)
    expect(placement.phone).toBe('bottom-left')
    expect(nav().dataset.drag).toBeUndefined()
    expect(nav().style.getPropertyValue('translate')).toBe('')
  })

  it.each([
    ['Escape', () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))],
    ['pointercancel', () => pointer(nav(), 'pointercancel', 405, 450)],
  ])('cancels drag without changing placement on %s', async (_name, cancel) => {
    mockScreen(412)
    await mountNav()
    await hold()
    pointer(nav(), 'pointermove', 405, 450)
    cancel()
    pointer(nav(), 'pointerup', 405, 450)
    await flushPromises()
    vi.advanceTimersByTime(SNAP_MS)
    expect(placement.phone).toBe('bottom-center')
    expect(nav().dataset.drag).toBeUndefined()
    expect(zones()).toBeNull()
  })

  it('keeps placement unchanged when released in place after hold', async () => {
    mockScreen(412)
    await mountNav()
    await hold()
    pointer(nav(), 'pointerup', 206, 870)
    await flushPromises()
    expect(capture).not.toHaveBeenCalled()
    expect(placement.phone).toBe('bottom-center')
    expect(wrapper!.get('[role="status"]').text()).toBe('')
  })
})
