import { afterEach, describe, expect, it } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import DesktopTopBar from '@/components/DesktopTopBar.vue'
import type { TripDetail } from '@/entities'
import { trip } from '@/features/trips/tripFixtures'
import { resetDesktopBarContext, useDesktopBarContext, useDesktopBarTrip } from '@/lib/desktopBarContext'
import { createAppI18n } from '@/lib/i18n'

const stub = { template: '<div />' }
let wrapper: VueWrapper | undefined

async function mountBar(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: stub },
      { path: '/trips/new', component: stub },
      { path: '/trips/:tripId', component: stub },
      { path: '/trips/:tripId/members', component: stub },
      { path: '/settings', component: stub },
      { path: '/demo', component: stub },
    ],
  })
  await router.push(path)
  await router.isReady()
  wrapper = mount(DesktopTopBar, {
    global: { plugins: [router, createAppI18n('en')] },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  resetDesktopBarContext()
})

describe('DesktopTopBar', () => {
  it('shows brand mark, new trip CTA, and settings link on Home without Trips back pill', async () => {
    const view = await mountBar('/')
    expect(view.text()).toContain('vallet')
    expect(view.find('a[href="/trips/new"]').text()).toContain('New trip')
    expect(view.find('a[href="/settings"]').attributes('aria-label')).toBe('Settings')
    expect(view.text()).not.toContain('Trips')
  })

  it('shows Trips back pill, trip name, active member count, Share link, and Settled pill when closed', async () => {
    const scope = effectScope()
    const current = ref<TripDetail>({ ...trip, closed: true })
    scope.run(() => {
      useDesktopBarTrip(() => current.value)
    })

    const view = await mountBar('/trips/abc')
    expect(view.text()).toContain('Trips')
    expect(view.text()).toContain('Da Lat')
    expect(view.text()).toContain('2 people')
    expect(view.text()).toContain('Settled')
    expect(view.find('a[href="/trips/abc/members"]').exists()).toBe(true)
    scope.stop()
  })

  it('hides Share link and shows Demo pill for readonly sample trips', async () => {
    const scope = effectScope()
    scope.run(() => {
      useDesktopBarTrip(() => trip, true)
    })

    const view = await mountBar('/demo')
    expect(view.text()).toContain('Demo')
    expect(view.find('a[href="/trips/abc/members"]').exists()).toBe(false)
    scope.stop()
  })

  it('hides Settings link while already on /settings', async () => {
    const view = await mountBar('/settings')
    expect(view.find('a[href="/settings"]').exists()).toBe(false)
    expect(view.text()).toContain('Trips')
  })

  it('preserves a newer view scope when an older view scope disposes', async () => {
    const active = useDesktopBarContext()
    const first = effectScope()
    first.run(() => {
      useDesktopBarTrip(() => trip)
    })
    await nextTick()
    expect(active.value?.id).toBe('abc')

    const second = effectScope()
    const nextTrip: TripDetail = { ...trip, id: 'xyz', name: 'Phu Quoc' }
    second.run(() => {
      useDesktopBarTrip(() => nextTrip)
    })
    await nextTick()
    expect(active.value?.id).toBe('xyz')

    first.stop()
    await nextTick()
    expect(active.value?.id).toBe('xyz')
    expect(active.value?.name).toBe('Phu Quoc')

    second.stop()
    await nextTick()
    expect(active.value).toBeNull()
  })
})
