import { defineComponent } from 'vue'
import { vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import type { Expense, ExpenseCategory, TripSpendSummary } from '@/entities'
import BalancesView from '@/features/balances/BalancesView.vue'
import ExpenseDetailView from '@/features/expenses/ExpenseDetailView.vue'
import ExpenseFormView from '@/features/expenses/ExpenseFormView.vue'
import { addToPane, openInPane } from '@/features/expenses/splitRedirects'
import FundView from '@/features/fund/FundView.vue'
import TripSummaryView from '@/features/summary/TripSummaryView.vue'
import { percentsOf } from '@/features/summary/summaryRules'
import CreateTripView from '@/features/trips/CreateTripView.vue'
import HomeView from '@/features/trips/HomeView.vue'
import TripView from '@/features/trips/TripView.vue'
import { restoreRememberedPane } from '@/features/trips/paneMemory'
import { days, trip } from '@/features/trips/tripFixtures'
import { ApiError, api } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'
import { mockSplit } from '@/lib/splitTestHelpers'

export { mockSplit }

const stub = defineComponent({ template: '<div />' })

export const splitTestRoutes: RouteRecordRaw[] = [
  { path: '/', component: HomeView },
  { path: '/trips/new', component: CreateTripView },
  { path: '/trips/:tripId', component: TripView, beforeEnter: restoreRememberedPane },
  { path: '/trips/:tripId/expenses/new', component: ExpenseFormView, beforeEnter: addToPane },
  { path: '/trips/:tripId/expenses/:expenseId/edit', component: ExpenseFormView, beforeEnter: openInPane },
  { path: '/trips/:tripId/expenses/:expenseId', component: ExpenseDetailView, beforeEnter: openInPane },
  { path: '/trips/:tripId/fund', component: FundView },
  { path: '/trips/:tripId/balances', component: BalancesView },
  { path: '/trips/:tripId/summary', component: TripSummaryView },
  { path: '/trips/:tripId/members', component: stub },
  { path: '/settings', component: stub },
  { path: '/join', component: stub },
  { path: '/demo', component: stub },
  { path: '/:pathMatch(.*)*', component: stub },
]

let wrapper: VueWrapper | undefined

function balancesOf(all: Expense[]) {
  const members = trip.members.map((member) => ({
    member_id: member.id,
    paid: all.filter((item) => item.paid_by === member.id).reduce((sum, item) => sum + item.amount, 0),
    contributed: 0,
    share: all
      .flatMap((item) => item.shares)
      .filter((share) => share.member_id === member.id)
      .reduce((sum, share) => sum + share.amount, 0),
    sent: 0,
    received: 0,
    net: 0,
    removed: member.removed,
  }))
  return { currency: 'VND', fund: { holder_id: null, remaining: 0 }, members, transfers: [] }
}

function summaryOf(all: Expense[]): TripSpendSummary {
  const dayOf = (date: string) => all.filter((item) => item.spent_on === date)
  const dayList = days
    .map((day) => ({
      date: day.date,
      count: dayOf(day.date).length,
      total: dayOf(day.date).reduce((sum, item) => sum + item.amount, 0),
    }))
    .filter((day) => day.count > 0)
  const byCategory = new Map<ExpenseCategory, { count: number; amount: number }>()
  for (const item of all) {
    const prev = byCategory.get(item.category) ?? { count: 0, amount: 0 }
    byCategory.set(item.category, { count: prev.count + 1, amount: prev.amount + item.amount })
  }
  const sorted = [...byCategory.entries()]
    .filter(([, entry]) => entry.amount > 0)
    .sort((a, b) => b[1].amount - a[1].amount)
  const percents = percentsOf(sorted.map(([, entry]) => entry.amount))
  const total = all.reduce((sum, item) => sum + item.amount, 0)
  const activeCount = trip.members.filter((member) => !member.removed).length
  const dayCount = dayList.length
  return {
    currency: 'VND',
    total,
    expense_count: all.length,
    active_member_count: activeCount,
    day_count: dayCount,
    per_person: activeCount > 0 ? Math.round(total / activeCount) : 0,
    per_day: dayCount > 0 ? Math.round(total / dayCount) : 0,
    categories: sorted.map(([category, entry], index) => ({
      category,
      count: entry.count,
      amount: entry.amount,
      percent: percents[index] ?? 0,
    })),
    payers: [],
    days: dayList,
  }
}

/** Serves trip endpoints from mutable `state.all` so specs can simulate creates, edits, and deletes. */
export function serve(state: { all: Expense[] }, tripOverrides: object = {}) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    const dayOf = (date: string) => state.all.filter((item) => item.spent_on === date)
    if (path === '/trips/abc') return Promise.resolve({ ...trip, ...tripOverrides })
    if (path === '/trips/abc/expenses/days') {
      const summaries = days
        .map((day) => ({ ...day, count: dayOf(day.date).length }))
        .filter((day) => day.count > 0)
      return Promise.resolve({ days: summaries })
    }
    if (path === '/trips/abc/balances') return Promise.resolve(balancesOf(state.all))
    if (path === '/trips/abc/summary') return Promise.resolve(summaryOf(state.all))
    const byDay = /^\/trips\/abc\/expenses\?day=(.+)$/.exec(path)
    if (byDay?.[1]) return Promise.resolve({ expenses: dayOf(byDay[1]) })
    const one = /^\/trips\/abc\/expenses\/(.+)$/.exec(path)
    const found = state.all.find((item) => item.id === one?.[1])
    if (found) return Promise.resolve(found)
    return Promise.reject(new ApiError(404, 'not_found', 'Not Found'))
  })
}

export async function mountTrip(path = '/trips/abc') {
  const router = createRouter({ history: createMemoryHistory(), routes: splitTestRoutes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [createAppI18n('en'), router] } })
  await flushPromises()
  return { view: wrapper, router }
}

export function unmountTrip() {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
}
