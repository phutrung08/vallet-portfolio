import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import NavPlacementCard from '@/features/settings/NavPlacementCard.vue'
import { createAppI18n } from '@/lib/i18n'
import { NAV_STORAGE_KEY, initNavPlacement } from '@/lib/useNavPlacement'

function mockWidth(width: number) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => {
      const min = query.includes('37.5rem') ? 600 : 400
      return {
        matches: width >= min,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }
    }),
  )
}

function mountCard() {
  return mount(NavPlacementCard, { global: { plugins: [createAppI18n('en')] } })
}

beforeEach(() => {
  localStorage.clear()
  initNavPlacement()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('NavPlacementCard', () => {
  it('shows only a note on a small screen', () => {
    mockWidth(360)
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('On this small screen the navigation always sits at the bottom center.')
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.find('[data-testid="nav-preview"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Tip:')
  })

  it.each([412, 800])('shows the drag tip from the large-phone width up (%ipx)', (width) => {
    mockWidth(width)
    expect(mountCard().text()).toContain('Tip: press and hold the navigation bar, then drag to move it.')
  })

  it('shows the five phone choices in two rows on a large phone', () => {
    mockWidth(412)
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('On large phones')
    expect(wrapper.findAll('[role="group"]')).toHaveLength(2)
    expect(wrapper.findAll('button').map((b) => b.text())).toEqual([
      'Left',
      'Center',
      'Right',
      'Left edge',
      'Right edge',
    ])
    expect(wrapper.get('[data-testid="nav-preview"]').attributes('data-value')).toBe('bottom-center')
  })

  it('shows the two rail choices on a wide screen', () => {
    mockWidth(800)
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('On wide screens')
    expect(wrapper.findAll('button').map((b) => b.text())).toEqual(['Left', 'Right'])
    expect(wrapper.get('[data-testid="nav-preview"]').attributes('data-value')).toBe('rail-left')
  })

  it('updates the preview and the stored choice as options are tapped', async () => {
    mockWidth(412)
    const wrapper = mountCard()
    await wrapper.findAll('button').find((b) => b.text() === 'Right edge')?.trigger('click')
    expect(wrapper.get('[data-testid="nav-preview"]').attributes('data-value')).toBe('edge-right')
    expect(JSON.parse(localStorage.getItem(NAV_STORAGE_KEY) ?? '').phone).toBe('edge-right')
    await wrapper.findAll('button').find((b) => b.text() === 'Left')?.trigger('click')
    expect(wrapper.get('[data-testid="nav-preview"]').attributes('data-value')).toBe('bottom-left')
  })

  it('updates the wide preview too', async () => {
    mockWidth(800)
    const wrapper = mountCard()
    await wrapper.findAll('button').find((b) => b.text() === 'Right')?.trigger('click')
    expect(wrapper.get('[data-testid="nav-preview"]').attributes('data-value')).toBe('rail-right')
  })
})
