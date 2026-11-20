<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { TripDetail, TripMember } from '@/entities'
import ActivityLink from '@/features/members/ActivityLink.vue'
import AddMemberForm from '@/features/members/AddMemberForm.vue'
import MemberList from '@/features/members/MemberList.vue'
import SecuritySection from '@/features/members/SecuritySection.vue'
import ShareBlock from '@/features/members/ShareBlock.vue'
import { useMemberNameForm } from '@/features/members/useMemberNameForm'
import type { useShareLink } from '@/features/members/useShareLink'
import { activeMembers } from '@/features/trips/tripMeta'
import { api } from '@/lib/api'

/**
 * List column of the members screen. Compact viewports include invite and security sections;
 * split viewports offload those and member inspection into the detail pane.
 */
const props = defineProps<{
  trip: TripDetail
  share: ReturnType<typeof useShareLink>
  split: boolean
  selectedId: string | null
  refresh: () => Promise<void>
}>()
defineEmits<{ select: [member: TripMember] }>()

const { t } = useI18n()
const adding = useMemberNameForm(
  () => activeMembers(props.trip).map((member) => member.display_name),
  async (name) => {
    await api.post(`/trips/${encodeURIComponent(props.trip.id)}/members`, { display_name: name })
    await props.refresh()
  },
)

async function addMember(): Promise<void> {
  if (await adding.submit()) adding.reset()
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <ShareBlock
      v-if="!split"
      :share="share"
    />
    <section class="flex flex-col gap-2">
      <h2 class="text-lg">
        {{ t('members.listTitle') }}
      </h2>
      <p
        v-if="trip.locked"
        class="card-ink bg-sand p-3 text-sm"
      >
        {{ t('errors.trip_locked') }}
      </p>
      <MemberList
        :trip="trip"
        :can-edit="!trip.locked"
        :split="split"
        :selected-id="selectedId"
        :refresh="refresh"
        @select="$emit('select', $event)"
      />
      <AddMemberForm
        v-if="!trip.locked"
        v-model="adding.text.value"
        :error-key="adding.errorKey.value"
        :pending="adding.pending.value"
        @submit="addMember"
      />
    </section>
    <ActivityLink :trip-id="trip.id" />
    <SecuritySection
      v-if="!split"
      :trip-id="trip.id"
      :locked="trip.locked"
      :rotate="share.rotate"
      :refresh="refresh"
    />
  </div>
</template>
