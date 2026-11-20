import type {
  Balances,
  BankAccount,
  CategoryBreakdown,
  DaySummary,
  Expense,
  ExpenseCategory,
  FundDetail,
  PayerBreakdown,
  Payment,
  TripDetail,
  TripSpendSummary,
} from '@/entities'
import sample from '@/features/demo/demoTrip.json'
import { percentsOf } from '@/features/summary/summaryRules'
import { activeMemberCount } from '@/features/trips/tripMeta'
import type { TripSource } from '@/lib/tripSource'

/** Snapshot of all GET responses for the self-contained interactive demo trip. */
interface DemoTrip {
  trip: TripDetail
  days: DaySummary[]
  fund: FundDetail
  expenses: Record<string, Expense[]>
  balances: Balances
  payments: Payment[]
  accounts: BankAccount[]
}

const demo = sample as DemoTrip

function findExpense(id: string, path: string): Expense {
  const found = Object.values(demo.expenses)
    .flat()
    .find((expense) => expense.id === id)
  if (!found) throw new Error(`The sample trip has no ${path}`)
  return found
}

function summariseDemo(): TripSpendSummary {
  const allExpenses = Object.values(demo.expenses).flat()
  const byCategory = new Map<ExpenseCategory, { count: number; amount: number }>()
  const byPayer = new Map<string | null, { count: number; amount: number }>()

  for (const item of allExpenses) {
    const categoryStats = byCategory.get(item.category) ?? { count: 0, amount: 0 }
    byCategory.set(item.category, {
      count: categoryStats.count + 1,
      amount: categoryStats.amount + item.amount,
    })
    const payerStats = byPayer.get(item.paid_by) ?? { count: 0, amount: 0 }
    byPayer.set(item.paid_by, {
      count: payerStats.count + 1,
      amount: payerStats.amount + item.amount,
    })
  }

  const sortedCategories = [...byCategory.entries()]
    .filter(([, entry]) => entry.amount > 0)
    .sort((a, b) => b[1].amount - a[1].amount)
  const percents = percentsOf(sortedCategories.map(([, entry]) => entry.amount))
  const categories: CategoryBreakdown[] = sortedCategories.map(([category, entry], index) => ({
    category,
    count: entry.count,
    amount: entry.amount,
    percent: percents[index] ?? 0,
  }))

  const payers: PayerBreakdown[] = [...byPayer.entries()]
    .sort((a, b) => b[1].amount - a[1].amount)
    .map(([paid_by, entry]) => ({ paid_by, count: entry.count, amount: entry.amount }))

  const total = demo.days.reduce((sum, day) => sum + day.total, 0)
  const membersCount = activeMemberCount(demo.trip)
  const dayCount = demo.days.filter((day) => day.count > 0).length

  return {
    currency: demo.trip.currency,
    total,
    expense_count: allExpenses.length,
    active_member_count: membersCount,
    day_count: dayCount,
    per_person: membersCount > 0 ? Math.round(total / membersCount) : 0,
    per_day: dayCount > 0 ? Math.round(total / dayCount) : 0,
    categories,
    payers,
    days: demo.days,
  }
}

/** Answers trip-page GET requests purely in memory without touching the network. */
function answer(path: string): unknown {
  const [pathname = '', query = ''] = path.split('?')
  const rest = pathname.replace(/^\/trips\/[^/]+/, '')
  switch (rest) {
    case '':
      return demo.trip
    case '/expenses/days':
      return { days: demo.days }
    case '/expenses':
      return { expenses: demo.expenses[new URLSearchParams(query).get('day') ?? ''] ?? [] }
    case '/fund':
      return demo.fund
    case '/balances':
      return demo.balances
    case '/summary':
      return summariseDemo()
    case '/payments':
      return { payments: demo.payments }
    case '/bank-accounts':
      return { accounts: demo.accounts }
    default: {
      const expenseId = /^\/expenses\/([^/]+)$/.exec(rest)?.[1]
      if (expenseId !== undefined) return findExpense(decodeURIComponent(expenseId), path)
      throw new Error(`The sample trip has no ${path}`)
    }
  }
}

export const demoSource: TripSource = {
  read: <T>(path: string) => Promise.resolve(answer(path) as T),
  readonly: true,
  home: () => '/demo',
}
