import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, api } from '@/lib/api'
import {
  buildCreateBody,
  serverFieldErrors,
  validateTrip,
  type FormErrors,
  type TripForm,
} from '@/features/trips/tripFormRules'
import type { TripDetail } from '@/entities'

export function useCreateTripForm() {
  const router = useRouter()
  const form = reactive<TripForm>({
    name: '',
    startsOn: '',
    endsOn: '',
    usesFund: false,
    currency: 'VND',
    creatorName: '',
    memberNames: [],
  })
  const errors = ref<FormErrors>({})
  const submitError = ref<unknown>(null)
  const pending = ref(false)
  const attempted = ref(false)

  // Keep validation reactive once the user has attempted submission.
  watch(form, () => {
    if (attempted.value) errors.value = validateTrip(form)
  })

  function applyServerError(error: unknown): void {
    const mapped = error instanceof ApiError ? serverFieldErrors(error.fields) : {}
    if (Object.keys(mapped).length > 0) errors.value = mapped
    else submitError.value = error
  }

  async function submit(): Promise<void> {
    if (pending.value) return
    attempted.value = true
    submitError.value = null
    errors.value = validateTrip(form)
    if (Object.keys(errors.value).length > 0) return
    pending.value = true
    try {
      const trip = await api.post<TripDetail>('/trips', buildCreateBody(form))
      await router.replace(`/trips/${trip.id}`)
    } catch (caught) {
      applyServerError(caught)
    } finally {
      pending.value = false
    }
  }

  return { form, errors, submitError, pending, submit }
}
