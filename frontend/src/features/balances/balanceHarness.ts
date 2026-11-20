import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { RouterView, createMemoryHistory, createRouter, type RouteRecordRaw, type Router } from 'vue-router'
import BalancesView from '@/features/balances/BalancesView.vue'
import { createAppI18n } from '@/lib/i18n'

const stub = defineComponent({ template: '<div />' })

const routes: RouteRecordRaw[] = [
  { path: '/trips/:tripId/balances', component: BalancesView },
  { path: '/trips/:tripId', component: stub },
  { path: '/trips/:tripId/fund', component: stub },
  { path: '/trips/:tripId/members', component: stub },
  { path: '/trips/:tripId/summary', component: stub },
  { path: '/trips/:tripId/expenses/new', component: stub },
  { path: '/settings', component: stub },
  { path: '/', component: stub },
]

let mounted: VueWrapper | undefined
let router: Router | undefined

/** Returns the router instance of the most recently mounted balances view. */
export const balancesRouter = () => router as Router

/** Mounts BalancesView at the given path attached to document.body for native dialog queries. */
export async function mountBalances(path = '/trips/abc/balances'): Promise<VueWrapper> {
  router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  mounted = mount(RouterView, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return mounted
}

export function unmountBalances(): void {
  mounted?.unmount()
  mounted = undefined
  document.body.innerHTML = ''
}
