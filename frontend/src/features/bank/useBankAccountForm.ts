import { reactive, ref } from 'vue'
import type { BankAccount } from '@/entities'
import {
  finalAccountName,
  validateAccount,
  type AccountFormErrors,
} from '@/features/bank/accountRules'
import { api } from '@/lib/api'

/**
 * Receiving bank account form state. Stored account numbers are never returned by the API
 * after masking, so changing an account requires entering the full number again.
 */
export function useBankAccountForm(
  tripId: () => string,
  current: BankAccount | null,
  onSaved: () => Promise<void>,
) {
  const form = reactive<{ bin: string | null; number: string; name: string }>({
    bin: current?.bank_bin ?? null,
    number: '',
    name: current?.account_name ?? '',
  })
  const errors = ref<AccountFormErrors>({})
  const submitError = ref<unknown>(null)
  const pending = ref(false)

  async function submit(): Promise<void> {
    if (pending.value) return
    submitError.value = null
    errors.value = validateAccount(form)
    if (Object.keys(errors.value).length > 0 || form.bin === null) return
    pending.value = true
    try {
      const body = {
        bank_bin: form.bin,
        account_number: form.number,
        account_name: finalAccountName(form.name),
      }
      await api.put(`/trips/${encodeURIComponent(tripId())}/members/me/bank-account`, body)
      await onSaved()
    } catch (caught) {
      submitError.value = caught
    } finally {
      pending.value = false
    }
  }

  return { form, errors, submitError, pending, submit }
}
