import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ExpenseFormView from '@/features/expenses/ExpenseFormView.vue'
import { createAppI18n } from '@/lib/i18n'

const stub = { template: '<div />' }

/** Mounts the standalone expense form at `path` with a pinned date; caller mocks API first. */
export async function mountExpenseForm(path: string, today = '2026-11-06') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/trips/:tripId', component: stub },
      { path: '/trips/:tripId/expenses/new', component: ExpenseFormView },
      { path: '/trips/:tripId/expenses/:expenseId', component: stub },
      { path: '/trips/:tripId/expenses/:expenseId/edit', component: ExpenseFormView },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(ExpenseFormView, {
    props: { now: () => new Date(`${today}T12:00:00`) },
    attachTo: document.body,
    global: { plugins: [createAppI18n('en'), router] },
  })
  await flushPromises()
  return { wrapper, router }
}

/** Finds a form input or textarea by its associated `<label for>` text. */
export function field(form: VueWrapper, label: string) {
  const labelEl = form.findAll('label').find((item) => item.text() === label)
  return form.get(`#${CSS.escape(labelEl?.attributes('for') ?? 'missing')}`)
}

export async function fillValid(form: VueWrapper, amount = '395000') {
  await field(form, 'Amount').setValue(amount)
  await field(form, 'What for').setValue('Noodles')
}
