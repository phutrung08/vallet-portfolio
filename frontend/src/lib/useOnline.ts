import { getCurrentScope, onScopeDispose, ref } from 'vue'

/** Reactive wrapper around ``navigator.onLine`` listening to online/offline transitions. */
export function useOnline() {
  const online = ref(navigator.onLine)
  const update = () => {
    online.value = navigator.onLine
  }
  window.addEventListener('online', update)
  window.addEventListener('offline', update)
  if (getCurrentScope()) {
    onScopeDispose(() => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    })
  }
  return online
}
