import { computed, getCurrentScope, onScopeDispose, ref, shallowReactive, watch } from 'vue'
import type { Expense } from '@/entities'
import { liveRead, type Reader } from '@/lib/tripSource'
import type { LoadStatus } from '@/lib/useAsyncData'

/** Manages per-day expense lists with in-memory day cache and abort-safe day switching. */
export function useDayExpenses(tripId: () => string, day: () => string, read: Reader = liveRead) {
  const cache = shallowReactive(new Map<string, Expense[]>())
  const status = ref<LoadStatus>('loading')
  const error = ref<unknown>(null)

  let requestId = 0
  let activeController: AbortController | null = null

  /** Fetches expenses for `date`, optionally bypassing cache while preserving displayed rows. */
  async function load(date: string, force = false): Promise<void> {
    if (cache.has(date) && !force) {
      activeController?.abort()
      activeController = null
      status.value = 'ready'
      return
    }
    activeController?.abort()
    const controller = new AbortController()
    activeController = controller
    const id = ++requestId
    if (!cache.has(date)) status.value = 'loading'
    try {
      const query = `day=${encodeURIComponent(date)}`
      const out = await read<{ expenses: Expense[] }>(
        `/trips/${encodeURIComponent(tripId())}/expenses?${query}`,
        controller.signal,
      )
      if (id !== requestId || controller.signal.aborted) return
      cache.set(date, out.expenses)
      if (date === day()) {
        error.value = null
        status.value = 'ready'
      }
    } catch (caught) {
      if (id !== requestId || controller.signal.aborted || date !== day()) return
      error.value = caught
      status.value = 'error'
    } finally {
      if (activeController === controller) activeController = null
    }
  }

  watch(day, (date) => {
    void load(date)
  }, { immediate: true })

  if (getCurrentScope()) {
    onScopeDispose(() => {
      requestId += 1
      activeController?.abort()
      activeController = null
    })
  }

  /** Invalidates cached expenses for `date`, reloading immediately if `date` is active. */
  async function invalidate(date: string): Promise<void> {
    cache.delete(date)
    if (date === day()) await load(date)
  }

  /** Refreshes the active day and clears stale entries for all other days. */
  async function refreshAll(): Promise<void> {
    const shown = day()
    for (const date of [...cache.keys()]) if (date !== shown) cache.delete(date)
    await load(shown, true)
  }

  const expenses = computed(() => cache.get(day()) ?? [])
  const reload = () => load(day())
  return { expenses, status, error, reload, invalidate, refreshAll }
}
