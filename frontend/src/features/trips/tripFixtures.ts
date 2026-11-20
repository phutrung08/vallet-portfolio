import type { TripDetail } from '@/entities'

export const trip: TripDetail = {
  id: 'abc',
  name: 'Da Lat',
  currency: 'VND',
  starts_on: '2026-11-05',
  ends_on: '2026-11-08',
  fund_holder_id: null,
  locked: false,
  closed: false,
  me: '1',
  members: [
    { id: '1', display_name: 'Alex', position: 0, removed: false },
    { id: '2', display_name: 'Ben', position: 1, removed: false },
    { id: '3', display_name: 'Former guest', position: 2, removed: true },
  ],
}

export const days = [
  { date: '2026-11-06', count: 2, total: 300_000 },
  { date: '2026-11-05', count: 1, total: 200_000 },
]

/** Mock GET responder for trip-page endpoints; rejects unexpected paths to catch stray fetches. */
export function respond(overrides: Partial<TripDetail> = {}, fund: object | null = null) {
  return (path: string): Promise<unknown> => {
    if (path === '/trips/abc') return Promise.resolve({ ...trip, ...overrides })
    if (path === '/trips/abc/expenses/days') return Promise.resolve({ days })
    if (path.startsWith('/trips/abc/expenses?day=')) return Promise.resolve({ expenses: [] })
    if (path === '/trips/abc/fund' && fund) return Promise.resolve(fund)
    return Promise.reject(new Error(`unexpected GET ${path}`))
  }
}
