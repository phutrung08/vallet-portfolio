<script setup lang="ts">
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Pencil, UserMinus } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import type { TripDetail, TripMember } from '@/entities'
import MemberFacts from '@/features/members/MemberFacts.vue'
import MemberTag from '@/features/members/MemberTag.vue'
import RenameForm from '@/features/members/RenameForm.vue'
import { useMemberEdit } from '@/features/members/useMemberEdit'
import { errorMessageKey } from '@/lib/errors'

/** Split detail pane view for a single member: financial summary plus rename and remove actions. */
const props = defineProps<{ trip: TripDetail; member: TripMember; refresh: () => Promise<void> }>()
defineEmits<{ close: [] }>()

const { t } = useI18n()
const { renaming, rename, removal, startRename, saveRename } = useMemberEdit(
  () => props.trip,
  props.refresh,
)
const isMe = () => props.member.id === props.trip.me
watch(
  () => props.member.id,
  () => {
    renaming.value = null
  },
)
</script>

<template>
  <BaseButton
    variant="outline"
    class="self-start"
    @click="$emit('close')"
  >
    <ArrowLeft
      :size="16"
      class="mr-1.5"
      aria-hidden="true"
    />
    {{ t('members.detail.back') }}
  </BaseButton>
  <header class="flex items-center">
    <MemberTag
      :member="member"
      :is-me="isMe()"
      :is-holder="member.id === trip.fund_holder_id"
      name-tag="h2"
    />
  </header>
  <MemberFacts
    :key="member.id"
    :trip="trip"
    :member-id="member.id"
  />
  <template v-if="!trip.locked">
    <section
      v-if="renaming"
      class="flex flex-col gap-2"
    >
      <RenameForm
        v-model="rename.text.value"
        :error-key="rename.errorKey.value"
        :pending="rename.pending.value"
        @submit="saveRename"
      />
      <BaseButton
        variant="outline"
        block
        @click="renaming = null"
      >
        {{ t('common.cancel') }}
      </BaseButton>
    </section>
    <BaseButton
      v-else
      variant="outline"
      block
      @click="startRename(member)"
    >
      <Pencil
        :size="18"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ t('members.renameOf', { name: member.display_name }) }}
    </BaseButton>
    <BaseButton
      v-if="!isMe()"
      variant="danger-outline"
      block
      @click="removal.ask(member)"
    >
      <UserMinus
        :size="18"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ t('members.removeOf', { name: member.display_name }) }}
    </BaseButton>
  </template>
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
