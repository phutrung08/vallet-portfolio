import { reactive, ref } from 'vue'
import { MAX_AMOUNT } from '@/features/expenses/amountText'
import { contributionBody } from '@/features/fund/fundRules'
import { api, newIdempotencyKey } from '@/lib/api'

export type ContributionError = 'amountRequired' | 'amountTooLarge' | 'dateRequired'

/** Modal form controller for recording a fund contribution with stable retry idempotency key. */
export function useContributionForm(
  tripId: () => string,
  defaults: () => { memberId: string; today: string },
  onSaved: () => Promise<void>,
) {
  const open = ref(false)
  const form = reactive<{ memberId: string; amount: number | null; date: string }>({
    memberId: '',
    amount: null,
    date: '',
  })
  const errors = ref<Partial<Record<'amount' | 'date', ContributionError>>>({})
  const submitError = ref<unknown>(null)
  const pending = ref(false)
  let idempotencyKey = newIdempotencyKey()

  function show(): void {
    const { memberId, today } = defaults()
    Object.assign(form, { memberId, amount: null, date: today })
    errors.value = {}
    submitError.value = null
    idempotencyKey = newIdempotencyKey()
    open.value = true
  }

  function close(): void {
    if (!pending.value) open.value = false
  }

  function validate(): typeof errors.value {
    const found: typeof errors.value = {}
    if (form.amount === null || form.amount <= 0) found.amount = 'amountRequired'
    else if (form.amount > MAX_AMOUNT) found.amount = 'amountTooLarge'
    if (form.date === '') found.date = 'dateRequired'
    return found
  }

  async function submit(): Promise<void> {
    if (pending.value) return
    submitError.value = null
    errors.value = validate()
    if (Object.keys(errors.value).length > 0 || form.amount === null) return
    pending.value = true
    try {
      const body = contributionBody(form.memberId, form.amount, form.date)
      const path = `/trips/${encodeURIComponent(tripId())}/fund/contributions`
      await api.post(path, body, { idempotencyKey })
      open.value = false
      await onSaved()
    } catch (caught) {
      submitError.value = caught
    } finally {
      pending.value = false
    }
  }

  return { open, form, errors, submitError, pending, show, close, submit }
}
