import { useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { forgetTripCopy } from '@/lib/offlineCache'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

export type SecurityAction = 'rotate' | 'lock' | 'unlock' | 'leave'

/** Handles confirmed link security actions: invite rotation, trip lock/unlock, and leaving on this device. */
export function useTripSecurity(
  tripId: () => string,
  rotate: () => Promise<void>,
  onChanged: () => Promise<void>,
) {
  const router = useRouter()
  return useConfirmedAction<SecurityAction>(async (action) => {
    const base = `/trips/${encodeURIComponent(tripId())}`
    if (action === 'rotate') {
      await rotate()
    } else if (action === 'leave') {
      await api.post<void>(`${base}/leave`)
      // Evict local offline cache for this trip so revoked access cannot be reopened offline.
      await forgetTripCopy(tripId()).catch(() => undefined)
      await router.replace('/')
    } else {
      await api.post(`${base}/${action}`)
      await onChanged()
    }
  })
}
