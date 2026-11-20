import { ref, shallowRef } from 'vue'

/** Two-step confirmed async action state: ``ask`` sets target, ``confirm`` runs ``run(target)``. */
export function useConfirmedAction<T>(run: (target: T) => Promise<void>) {
  const target = shallowRef<T | null>(null)
  const pending = ref(false)
  const error = ref<unknown>(null)

  function ask(item: T): void {
    target.value = item
    error.value = null
  }

  function cancel(): void {
    if (!pending.value) target.value = null
  }

  async function confirm(): Promise<void> {
    const item = target.value
    if (item === null || pending.value) return
    pending.value = true
    try {
      await run(item)
      target.value = null
    } catch (caught) {
      error.value = caught
    } finally {
      pending.value = false
    }
  }

  return { target, pending, error, ask, cancel, confirm }
}
