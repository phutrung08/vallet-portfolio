import { onBeforeUnmount, ref } from 'vue'

const FEEDBACK_MS = 2000

/** Copy ``text()`` to the clipboard and briefly expose ``copied`` or ``failed`` state. */
export function useCopy(text: () => string | null) {
  const copyState = ref<'idle' | 'copied' | 'failed'>('idle')
  let timer: ReturnType<typeof setTimeout> | undefined

  function flash(state: 'copied' | 'failed'): void {
    copyState.value = state
    clearTimeout(timer)
    timer = setTimeout(() => (copyState.value = 'idle'), FEEDBACK_MS)
  }

  async function copy(): Promise<void> {
    const value = text()
    if (value === null) return
    try {
      await navigator.clipboard.writeText(value)
      flash('copied')
    } catch {
      flash('failed')
    }
  }

  onBeforeUnmount(() => clearTimeout(timer))

  return { copyState, copy }
}
