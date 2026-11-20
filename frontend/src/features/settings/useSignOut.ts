import { useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { forgetAllTripCopies } from '@/lib/offlineCache'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

/**
 * Confirmed device sign-out: revokes the browser session cookie on the server, evicts all
 * locally cached offline API responses, and preserves UI language and theme preferences.
 */
export function useSignOut() {
  const router = useRouter()
  return useConfirmedAction<true>(async () => {
    await api.post<undefined>('/devices/me/sign-out')
    await forgetAllTripCopies()
    await router.push('/')
  })
}
