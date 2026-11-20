import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import HomeEmptyState from '@/features/trips/HomeEmptyState.vue'
import { api } from '@/lib/api'
import { button, click } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'
import { mockSplit } from '@/lib/splitTestHelpers'
import { routes } from '@/router'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

let mounted: VueWrapper | undefined

async function mountAt(path: string, wrapped: typeof RouterView | typeof HomeEmptyState = RouterView) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  mounted = mount(wrapped, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return { view: mounted, router }
}

beforeEach(() => {
  localStorage.clear()
  Element.prototype.scrollIntoView = vi.fn()
  mockSplit(false)
})

afterEach(() => {
  mounted?.unmount()
  mounted = undefined
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  for (const method of Object.values(api)) vi.mocked(method).mockClear()
})

function expectNoServerCalls(): void {
  for (const method of Object.values(api)) expect(method).not.toHaveBeenCalled()
}

describe('/demo trip page', () => {
  it('shows the banner, the trip, the fund card and the day tabs', async () => {
    const { view } = await mountAt('/demo')
    expect(view.text()).toContain('This is a sample trip. Nothing is saved.')
    expect(view.get('h1').text()).toBe('Phu Quoc 3D2N')
    expect(view.text()).toContain('Fund left')
    expect(view.text()).toContain('₫220,000')
    expect(view.text()).toContain('4 people')
    const tabs = view.findAll('[role="tab"]').map((tab) => tab.text())
    expect(tabs).toEqual(expect.arrayContaining(['Day 1', 'Day 2', 'Day 3']))
    expectNoServerCalls()
  })

  it('lists the expenses of a day and expands a row', async () => {
    const { view } = await mountAt('/demo')
    await click(view.findAll('[role="tab"]').find((tab) => tab.text() === 'Day 1')?.element)
    const rows = view.findAll('li button[aria-expanded]')
    expect(rows).toHaveLength(4)
    expect(view.text()).toContain('Kien Xay stir-noodle soup')
    expect(view.text()).toContain('Beachfront hotel (2 nights)')
    expect(rows[0]?.attributes('aria-expanded')).toBe('false')
    await rows[0]?.trigger('click')
    expect(rows[0]?.attributes('aria-expanded')).toBe('true')
    expectNoServerCalls()
  })

  it('shows who is left out of an expense', async () => {
    const { view } = await mountAt('/demo')
    await click(view.findAll('[role="tab"]').find((tab) => tab.text() === 'Day 2')?.element)
    const coffee = view.findAll('li button[aria-expanded]').find((row) => row.text().includes('Iced coffee'))
    await coffee?.trigger('click')
    expect(view.text()).toContain('Chloe')
    expect(view.text()).toContain('Chloe skipped coffee')
  })

  it('hides every write action', async () => {
    const { view } = await mountAt('/demo')
    await click(view.findAll('[role="tab"]').find((tab) => tab.text() === 'Day 1')?.element)
    await view.get('li button[aria-expanded]').trigger('click')
    expect(view.find('[aria-label="Share trip"]').exists()).toBe(false)
    expect(view.find('nav button').exists()).toBe(false)
    expect(view.find('[aria-label="Edit expense"]').exists()).toBe(false)
    expect(view.find('[aria-label="Delete expense"]').exists()).toBe(false)
    expect(view.find('a[href*="/fund"]').exists()).toBe(false)
    const hrefs = view.findAll('nav a').map((link) => link.attributes('href'))
    expect(hrefs).toEqual(['/demo', '/demo/balances'])
  })

  it('sends the banner button to the create-trip page', async () => {
    const { view, router } = await mountAt('/demo')
    await view.get('a[href="/trips/new"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/new'))
  })
})

describe('/demo balances and split stats', () => {
  it('shows who pays whom and each person, without any action', async () => {
    const { view } = await mountAt('/demo/balances')
    expect(view.text()).toContain('This is a sample trip')
    expect(view.get('h1').text()).toBe('Balances')
    expect(view.text()).toContain('Phu Quoc 3D2N')
    expect(view.text()).toContain('₫325,500')
    expect(view.text()).toContain('David')
    await click(button(view.element, 'Per person'))
    expect(view.text()).toContain('₫888,500')
    expect(view.text()).not.toContain('Trip summary')
    expect(view.text()).not.toContain('Close the trip')
    expect(view.find('nav button').exists()).toBe(false)
    expectNoServerCalls()
  })

  it('answers the split Stats pane from demo data without calling the server', async () => {
    mockSplit(true)
    const { view } = await mountAt('/demo')
    const statsButton = view
      .get('.split-detail')
      .findAll('[role="group"] button')
      .find((item) => item.text() === 'Stats')
    await statsButton?.trigger('click')
    await flushPromises()
    const pane = view.get('.split-detail')
    expect(pane.findAll('[role="group"] button').map((item) => item.text())).toEqual(['Details', 'Stats'])
    expect(pane.text()).toContain('By category')
    expect(pane.text()).toContain('Who paid how much')
    expect(pane.text()).toContain('Chloe')
    expectNoServerCalls()
  })
})

describe('VITE_DEMO_ONLY static deployment mode', () => {
  it('redirects / to /demo and hides the create-trip CTA in DemoLayout', async () => {
    vi.stubEnv('VITE_DEMO_ONLY', 'true')
    const { view, router } = await mountAt('/')
    expect(router.currentRoute.value.name).toBe('demo')
    expect(view.get('h1').text()).toBe('Phu Quoc 3D2N')
    expect(view.find('a[href="/trips/new"]').exists()).toBe(false)
    expectNoServerCalls()
  })
})

describe('home link to the sample', () => {
  it('opens /demo', async () => {
    const { view, router } = await mountAt('/', HomeEmptyState)
    await view.get('a[href="/demo"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('demo'))
  })
})
