import { computed, reactive, ref, watch } from 'vue'
import type { Expense, TripDetail } from '@/entities'
import {
  buildExpenseBody,
  initialForm,
  serverFieldErrors,
  splitCandidates,
  validateExpense,
  type ExpenseFormState,
  type FormErrors,
} from '@/features/expenses/expenseFormRules'
import {
  buildSplit,
  draftFromExpense,
  initialDraft,
  previewAmounts,
  splitProblem,
  toggled,
  type SplitDraft,
} from '@/features/expenses/splitDraft'
import { ApiError, api, newIdempotencyKey } from '@/lib/api'

/** Add or edit expense form controller with reactive validation and idempotent submission. */
export function useExpenseForm(
  trip: TripDetail,
  today: string,
  onSaved: (saved: Expense) => Promise<void> | void,
  expense?: Expense,
) {
  // Stable per-form-instance idempotency key prevents double submission on network retries.
  const idempotencyKey = newIdempotencyKey()
  const candidates = splitCandidates(trip, expense)
  const form = reactive<ExpenseFormState>(initialForm(trip, today, expense))
  const draft = reactive<SplitDraft>(expense ? draftFromExpense(expense) : initialDraft(candidates))
  const errors = ref<FormErrors>({})
  const submitError = ref<unknown>(null)
  const pending = ref(false)
  const attempted = ref(false)
  const preview = computed(() => previewAmounts(draft, candidates, form.amount))
  const conflict = computed(() => submitError.value instanceof ApiError && submitError.value.code === 'version_conflict')

  function validate(): FormErrors {
    const found = validateExpense(form)
    const problem = splitProblem(draft, candidates, form.amount)
    return problem ? { ...found, split: problem } : found
  }

  // Keep error display live once submission has been attempted.
  watch([form, draft], () => {
    if (attempted.value) errors.value = validate()
  })

  function toggle(id: string): void {
    draft.included = toggled(draft.included, id)
  }

  /** Sets share count, basis points, or minor-unit amount for `id` in the active split mode. */
  function setWeight(id: string, value: number | null): void {
    if (draft.mode === 'shares') draft.shares[id] = value ?? 0
    else if (draft.mode === 'percent') draft.basisPoints[id] = value
    else if (draft.mode === 'exact') draft.amounts[id] = value
  }

  function applyServerError(error: unknown): void {
    const mapped = serverFieldErrors(error)
    if (Object.keys(mapped).length > 0) errors.value = mapped
    else submitError.value = error
  }

  function save(): Promise<Expense> {
    const body = buildExpenseBody(form, buildSplit(draft, candidates))
    const base = `/trips/${encodeURIComponent(trip.id)}/expenses`
    if (!expense) return api.post<Expense>(base, body, { idempotencyKey })
    return api.put<Expense>(`${base}/${encodeURIComponent(expense.id)}`, { ...body, version: expense.version })
  }

  async function submit(): Promise<void> {
    if (pending.value) return
    attempted.value = true
    submitError.value = null
    errors.value = validate()
    if (Object.keys(errors.value).length > 0) return
    pending.value = true
    try {
      const saved = await save()
      await onSaved(saved)
    } catch (caught) {
      applyServerError(caught)
    } finally {
      pending.value = false
    }
  }

  return {
    form,
    draft,
    candidates,
    preview,
    errors,
    submitError,
    conflict,
    pending,
    toggle,
    setWeight,
    submit,
  }
}
