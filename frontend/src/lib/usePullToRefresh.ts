import { computed, ref, watch, type Ref } from 'vue'

/** Vertical pull travel (px) before releasing triggers a refresh. */
export const PULL_THRESHOLD = 70
const MAX_OFFSET = 96

/**
 * Touch pull-to-refresh bound to a scroll container, plus an imperative ``refresh`` action
 * shared with accessible refresh buttons.
 */
export function usePullToRefresh(
  target: Readonly<Ref<HTMLElement | null>>,
  onRefresh: () => Promise<unknown>,
) {
  const pulled = ref(0)
  const refreshing = ref(false)
  let startY: number | null = null
  const atTop = () => window.scrollY <= 0 && (target.value?.scrollTop ?? 0) <= 0

  async function refresh(): Promise<void> {
    if (refreshing.value) return
    refreshing.value = true
    try {
      await onRefresh()
    } finally {
      refreshing.value = false
    }
  }

  function start(event: TouchEvent): void {
    const touch = event.touches[0]
    startY = atTop() && !refreshing.value && touch ? touch.clientY : null
  }

  function move(event: TouchEvent): void {
    const touch = event.touches[0]
    if (startY === null || !touch) return
    if (!atTop()) {
      cancel()
      return
    }
    pulled.value = Math.max(0, touch.clientY - startY)
  }

  function end(): void {
    const armed = startY !== null && pulled.value >= PULL_THRESHOLD
    cancel()
    if (armed) void refresh()
  }

  function cancel(): void {
    startY = null
    pulled.value = 0
  }

  watch(
    target,
    (element, _previous, onCleanup) => {
      if (!element) return
      const passive = { passive: true }
      element.addEventListener('touchstart', start, passive)
      element.addEventListener('touchmove', move, passive)
      element.addEventListener('touchend', end)
      element.addEventListener('touchcancel', cancel)
      onCleanup(() => {
        element.removeEventListener('touchstart', start)
        element.removeEventListener('touchmove', move)
        element.removeEventListener('touchend', end)
        element.removeEventListener('touchcancel', cancel)
      })
    },
    { immediate: true },
  )

  return {
    offset: computed(() => Math.min(pulled.value / 2, MAX_OFFSET)),
    armed: computed(() => pulled.value >= PULL_THRESHOLD),
    refreshing,
    refresh,
  }
}
