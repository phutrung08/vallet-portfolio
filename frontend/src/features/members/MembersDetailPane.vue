<script setup lang="ts">
import type { TripDetail, TripMember } from '@/entities'
import MemberDetail from '@/features/members/MemberDetail.vue'
import SecuritySection from '@/features/members/SecuritySection.vue'
import ShareBlock from '@/features/members/ShareBlock.vue'
import type { useShareLink } from '@/features/members/useShareLink'

/** Right pane on split members layouts: selected member details or trip invite and link security. */
defineProps<{
  trip: TripDetail
  member: TripMember | null
  share: ReturnType<typeof useShareLink>
  refresh: () => Promise<void>
}>()
defineEmits<{ close: [] }>()
</script>

<template>
  <MemberDetail
    v-if="member"
    :trip="trip"
    :member="member"
    :refresh="refresh"
    @close="$emit('close')"
  />
  <template v-else>
    <ShareBlock :share="share" />
    <SecuritySection
      :trip-id="trip.id"
      :locked="trip.locked"
      :rotate="share.rotate"
      :refresh="refresh"
    />
  </template>
</template>
