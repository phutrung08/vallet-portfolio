import { ref } from 'vue'
import type { TripDetail, TripMember } from '@/entities'
import { useMemberNameForm } from '@/features/members/useMemberNameForm'
import { activeMembers } from '@/features/trips/tripMeta'
import { api } from '@/lib/api'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

/** Handles renaming and removing a member across compact sheets and split detail panes. */
export function useMemberEdit(trip: () => TripDetail, refresh: () => Promise<void>) {
  const memberPath = (member: TripMember) =>
    `/trips/${encodeURIComponent(trip().id)}/members/${encodeURIComponent(member.id)}`

  const renaming = ref<TripMember | null>(null)
  const rename = useMemberNameForm(
    () =>
      activeMembers(trip())
        .filter((member) => member.id !== renaming.value?.id)
        .map((member) => member.display_name),
    async (name) => {
      if (!renaming.value) return
      await api.patch(memberPath(renaming.value), { display_name: name })
      await refresh()
    },
  )
  const removal = useConfirmedAction<TripMember>(async (member) => {
    await api.delete<void>(memberPath(member))
    await refresh()
  })

  function startRename(member: TripMember): void {
    renaming.value = member
    rename.reset(member.display_name)
  }

  async function saveRename(): Promise<void> {
    if (await rename.submit()) renaming.value = null
  }

  return { renaming, rename, removal, startRename, saveRename }
}
