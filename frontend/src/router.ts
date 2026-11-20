import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { addToPane, openInPane } from '@/features/expenses/splitRedirects'
import HomeView from '@/features/trips/HomeView.vue'
import { restoreRememberedPane } from '@/features/trips/paneMemory'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    beforeEnter: () => (import.meta.env.VITE_DEMO_ONLY === 'true' ? { name: 'demo', replace: true } : true),
  },
  {
    path: '/demo',
    component: () => import('@/features/demo/DemoLayout.vue'),
    children: [
      {
        path: '',
        name: 'demo',
        component: () => import('@/features/trips/TripView.vue'),
        beforeEnter: restoreRememberedPane,
      },
      {
        path: 'balances',
        name: 'demo-balances',
        component: () => import('@/features/balances/BalancesView.vue'),
      },
    ],
  },
  {
    path: '/trips/new',
    name: 'create-trip',
    component: () => import('@/features/trips/CreateTripView.vue'),
  },
  {
    path: '/trips/:tripId',
    name: 'trip',
    component: () => import('@/features/trips/TripView.vue'),
    beforeEnter: restoreRememberedPane,
  },
  {
    path: '/trips/:tripId/expenses/new',
    name: 'new-expense',
    beforeEnter: addToPane,
    component: () => import('@/features/expenses/ExpenseFormView.vue'),
  },
  {
    path: '/trips/:tripId/expenses/:expenseId/edit',
    name: 'edit-expense',
    beforeEnter: openInPane,
    component: () => import('@/features/expenses/ExpenseFormView.vue'),
  },
  {
    path: '/trips/:tripId/expenses/:expenseId',
    name: 'expense',
    beforeEnter: openInPane,
    component: () => import('@/features/expenses/ExpenseDetailView.vue'),
  },
  {
    path: '/trips/:tripId/fund',
    name: 'fund',
    component: () => import('@/features/fund/FundView.vue'),
  },
  {
    path: '/trips/:tripId/balances',
    name: 'balances',
    component: () => import('@/features/balances/BalancesView.vue'),
  },
  {
    path: '/trips/:tripId/summary',
    name: 'summary',
    component: () => import('@/features/summary/TripSummaryView.vue'),
  },
  {
    path: '/trips/:tripId/members',
    name: 'members',
    component: () => import('@/features/members/MembersView.vue'),
  },
  {
    path: '/trips/:tripId/activity',
    name: 'activity',
    component: () => import('@/features/activity/ActivityView.vue'),
  },
  {
    path: '/join',
    name: 'join',
    component: () => import('@/features/join/JoinView.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/features/settings/SettingsView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/features/shell/NotFoundView.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (_to, _from, savedPosition) => savedPosition ?? { top: 0 },
})
