import { computed } from 'vue'
import type { ShareLink } from '@/entities'
import { buildShareLink } from '@/features/members/shareLink'
import { api } from '@/lib/api'
import { useAsyncData } from '@/lib/useAsyncData'
import { useCopy } from '@/lib/useCopy'

/** Manages fetching, copying, sharing via Web Share API, and rotating the trip invite link. */
export function useShareLink(tripId: () => string, tripName: () => string, shareText: () => string) {
  const base = () => `/trips/${encodeURIComponent(tripId())}/share-link`
  const { data, status, error, reload } = useAsyncData((signal) => api.get<ShareLink>(base(), { signal }))
  const link = computed(() => (data.value ? buildShareLink(location.origin, data.value.token) : null))
  const { copyState, copy } = useCopy(() => link.value)
  const canShare = typeof navigator.share === 'function'

  async function share(): Promise<void> {
    if (link.value === null) return
    try {
      await navigator.share({ title: tripName(), text: shareText(), url: link.value })
    } catch {
      // User dismissal and unsupported platforms reject identically; stay quiet.
    }
  }

  async function rotate(): Promise<void> {
    data.value = await api.post<ShareLink>(`${base()}/rotate`)
  }

  return { link, status, error, reload, copyState, canShare, copy, share, rotate }
}
