import { getCurrentScope, onScopeDispose, ref, type Ref } from 'vue'

/** Subscribe reactively to a CSS media query, returning false if matchMedia is unavailable. */
export function useMediaQuery(query: string): Ref<boolean> {
  const matches = ref(false)
  if (typeof window.matchMedia !== 'function') return matches
  const list = window.matchMedia(query)
  matches.value = list.matches
  const update = (event: MediaQueryListEvent) => {
    matches.value = event.matches
  }
  list.addEventListener('change', update)
  if (getCurrentScope()) {
    onScopeDispose(() => list.removeEventListener('change', update))
  }
  return matches
}
