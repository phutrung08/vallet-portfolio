import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAddExpense } from '@/features/expenses/useAddExpense'

const Stub = { setup: () => ({ add: useAddExpense(() => 'abc') }), template: '<button @click="add" />' }

async function pressFrom(path: string, wide: boolean) {
  vi.stubGlobal('matchMedia', () => ({ matches: wide, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/trips/:tripId/:rest*', component: Stub }],
  })
  await router.push(path)
  const view = mount(Stub, { global: { plugins: [router] } })
  await view.get('button').trigger('click')
  await flushPromises()
  return router.currentRoute.value
}

afterEach(() => vi.unstubAllGlobals())

describe('useAddExpense', () => {
  it('opens the standalone form on compact viewports', async () => {
    expect((await pressFrom('/trips/abc/balances', false)).path).toBe('/trips/abc/expenses/new')
  })

  it('navigates to trip Add pane when invoked from another split view', async () => {
    const route = await pressFrom('/trips/abc/balances?x=1', true)
    expect(route.path).toBe('/trips/abc')
    expect(route.query).toEqual({ pane: 'add' })
  })

  it('preserves existing day and expense selection when already on trip view', async () => {
    const route = await pressFrom('/trips/abc?day=2026-11-06&expense=e9', true)
    expect(route.query).toEqual({ day: '2026-11-06', expense: 'e9', pane: 'add' })
  })
})
