import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Transfer, VietQr } from '@/entities'
import { MAX_AMOUNT } from '@/features/expenses/amountText'
import { localIsoDate } from '@/features/trips/tripMeta'
import { ApiError, api, newIdempotencyKey } from '@/lib/api'

const QR_DELAY_MS = 300

export type AmountError = 'amountRequired' | 'amountTooLarge'

/**
 * Coordinates settlement payment amount editing, debounced + abort-safe VietQR generation,
 * and idempotent payment recording.
 */
export function useTransferPay(
  tripId: () => string,
  transfer: Transfer,
  onRecorded: () => Promise<void>,
) {
  const base = () => `/trips/${encodeURIComponent(tripId())}`
  const amount = ref<number | null>(transfer.amount)
  const qr = ref<VietQr | null>(null)
  const qrStatus = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const qrError = ref<unknown>(null)
  const recordError = ref<unknown>(null)
  const pending = ref(false)
  let idempotencyKey = newIdempotencyKey()
  let latest = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let qrController: AbortController | null = null

  const amountError = computed<AmountError | null>(() => {
    if (amount.value === null || amount.value <= 0) return 'amountRequired'
    return amount.value > Math.min(transfer.amount, MAX_AMOUNT) ? 'amountTooLarge' : null
  })
  const validAmount = computed(() => (amountError.value === null ? amount.value : null))
  const qrErrorCode = computed(() => (qrError.value instanceof ApiError ? qrError.value.code : null))

  async function loadQr(): Promise<void> {
    qrController?.abort()
    const value = validAmount.value
    const request = ++latest
    qr.value = null
    qrError.value = null
    qrStatus.value = value === null ? 'idle' : 'loading'
    if (value === null) {
      qrController = null
      return
    }
    const controller = new AbortController()
    qrController = controller
    try {
      const query = `payee=${encodeURIComponent(transfer.payee)}&amount=${value}`
      const out = await api.get<VietQr>(`${base()}/vietqr?${query}`, { signal: controller.signal })
      if (request !== latest || controller.signal.aborted) return
      qr.value = out
      qrStatus.value = 'ready'
    } catch (caught) {
      if (request !== latest || controller.signal.aborted) return
      qrError.value = caught
      qrStatus.value = 'error'
    } finally {
      if (qrController === controller) qrController = null
    }
  }

  watch(amount, () => {
    idempotencyKey = newIdempotencyKey()
    recordError.value = null
    // Discard stale QR payload immediately and wait for typing pause before refetching.
    latest += 1
    qrController?.abort()
    qrController = null
    qr.value = null
    qrStatus.value = validAmount.value === null ? 'idle' : 'loading'
    clearTimeout(timer)
    timer = setTimeout(() => void loadQr(), QR_DELAY_MS)
  })
  void loadQr()
  onBeforeUnmount(() => {
    clearTimeout(timer)
    qrController?.abort()
    qrController = null
  })

  async function record(): Promise<void> {
    const value = validAmount.value
    if (value === null || pending.value) return
    pending.value = true
    recordError.value = null
    try {
      const body = {
        payer: transfer.payer,
        payee: transfer.payee,
        amount: value,
        paid_on: localIsoDate(new Date()),
      }
      await api.post(`${base()}/payments`, body, { idempotencyKey })
      await onRecorded()
    } catch (caught) {
      recordError.value = caught
    } finally {
      pending.value = false
    }
  }

  return { amount, amountError, qr, qrStatus, qrError, qrErrorCode, recordError, pending, loadQr, record }
}
