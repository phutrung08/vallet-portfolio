import { computed, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TripDetail, TripMember } from '@/entities'
import { activeMembers } from '@/features/trips/tripMeta'

/**
 * Tracks the member shown in the split detail pane via `?member=<id>`.
 * Starts unselected so the invite card and link security section remain visible until chosen.
 */
export function useMemberSelection(active: Ref<boolean>, trip: () => TripDetail | undefined) {
  const route = useRoute()
  const router = useRouter()
  const selectedId = computed(() => (typeof route.query.member === 'string' ? route.query.member : null))
  const selected = computed<TripMember | null>(() => {
    const current = trip()
    return (current && activeMembers(current).find((member) => member.id === selectedId.value)) || null
  })

  async function select(member: TripMember | null): Promise<void> {
    if ((member?.id ?? null) === selectedId.value) return
    await router.push({ query: member ? { member: member.id } : {} })
  }

  watch([active, selected, selectedId, trip], () => {
    if (active.value && trip() && selectedId.value && !selected.value) void router.replace({ query: {} })
  })

  return { selected, selectedId, select }
}
