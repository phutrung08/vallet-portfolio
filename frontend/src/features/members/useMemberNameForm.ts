import { ref } from 'vue'
import { checkMemberName } from '@/features/members/memberRules'
import { errorMessageKey } from '@/lib/errors'

/** Shared state and validation logic for adding or renaming a trip member. */
export function useMemberNameForm(others: () => string[], save: (name: string) => Promise<void>) {
  const text = ref('')
  const errorKey = ref<string | null>(null)
  const pending = ref(false)

  function reset(initial = ''): void {
    text.value = initial
    errorKey.value = null
  }

  /** Validates locally, submits the normalized name, and returns true on success. */
  async function submit(): Promise<boolean> {
    if (pending.value) return false
    const checked = checkMemberName(text.value, others())
    if ('error' in checked) {
      errorKey.value = `members.errors.${checked.error}`
      return false
    }
    pending.value = true
    errorKey.value = null
    try {
      await save(checked.name)
      return true
    } catch (caught) {
      errorKey.value = errorMessageKey(caught)
      return false
    } finally {
      pending.value = false
    }
  }

  return { text, errorKey, pending, reset, submit }
}
