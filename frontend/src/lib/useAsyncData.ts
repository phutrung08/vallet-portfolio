import { getCurrentScope, onScopeDispose, ref } from 'vue'
import { onCachedCopy, type CachedCopy } from '@/lib/api'

export type LoadStatus = 'loading' | 'ready' | 'error'

function olderCopy(current: CachedCopy | null, next: CachedCopy): CachedCopy {
  if (current === null || current.savedAt === null) return current ?? next
  if (next.savedAt === null || next.savedAt < current.savedAt) return next
  return current
}

/**
 * Race-safe and abort-safe async loader: supersedes previous in-flight fetches on re-fetch
 * or scope disposal so stale responses never overwrite newer state.
 */
export function useAsyncData<T>(fetcher: (signal: AbortSignal) => Promise<T>) {
  const data = ref<T>()
  const status = ref<LoadStatus>('loading')
  const error = ref<unknown>(null)
  /** Oldest SW cache timestamp if any response came from offline cache; null when fresh. */
  const cachedCopy = ref<CachedCopy | null>(null)

  let requestId = 0
  let activeController: AbortController | null = null

  async function refresh(): Promise<void> {
    activeController?.abort()
    const controller = new AbortController()
    activeController = controller
    const id = ++requestId

    let copy: CachedCopy | null = null
    const stop = onCachedCopy((next) => {
      if (id === requestId) copy = olderCopy(copy, next)
    })

    try {
      const next = await fetcher(controller.signal)
      if (id !== requestId || controller.signal.aborted) return
      data.value = next
      error.value = null
      cachedCopy.value = copy
      status.value = 'ready'
    } catch (caught) {
      if (id !== requestId || controller.signal.aborted) return
      error.value = caught
      status.value = 'error'
    } finally {
      stop()
      if (activeController === controller) activeController = null
    }
  }

  async function reload(): Promise<void> {
    status.value = 'loading'
    await refresh()
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      requestId += 1
      activeController?.abort()
      activeController = null
    })
  }

  void reload()

  return { data, status, error, cachedCopy, reload, refresh }
}
