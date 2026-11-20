<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import type { TripDetail, TripMember } from '@/entities'
import MemberRow from '@/features/members/MemberRow.vue'
import RenameSheet from '@/features/members/RenameSheet.vue'
import { useMemberEdit } from '@/features/members/useMemberEdit'
import { activeMembers } from '@/features/trips/tripMeta'
import { errorMessageKey } from '@/lib/errors'

const props = defineProps<{
  trip: TripDetail
  canEdit: boolean
  split: boolean
  selectedId: string | null
  refresh: () => Promise<void>
}>()
defineEmits<{ select: [member: TripMember] }>()

const { t } = useI18n()
const { renaming, rename, removal, startRename, saveRename } = useMemberEdit(
  () => props.trip,
  props.refresh,
)
</script>

<template>
  <ul class="flex flex-col gap-1">
    <MemberRow
      v-for="member in activeMembers(trip)"
      :key="member.id"
      :member="member"
      :is-me="member.id === trip.me"
      :is-holder="member.id === trip.fund_holder_id"
      :can-edit="canEdit"
      :split="split"
      :selected="member.id === selectedId"
      @rename="startRename(member)"
      @remove="removal.ask(member)"
      @select="$emit('select', member)"
    />
  </ul>
  <RenameSheet
    v-model="rename.text.value"
    :open="renaming !== null"
    :error-key="rename.errorKey.value"
    :pending="rename.pending.value"
    @close="renaming = null"
    @submit="saveRename"
  />
  <ConfirmSheet
    :open="removal.target.value !== null"
    danger
    :title="t('members.removeTitle', { name: removal.target.value?.display_name ?? '' })"
    :message="t('members.removeBody')"
    :confirm-label="t('members.removeConfirm')"
    :pending="removal.pending.value"
    :error="removal.error.value ? t(errorMessageKey(removal.error.value)) : undefined"
    @confirm="removal.confirm"
    @cancel="removal.cancel"
  />
</template>
