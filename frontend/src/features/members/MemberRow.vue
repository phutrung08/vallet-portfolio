<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Pencil, UserMinus } from 'lucide-vue-next'
import type { TripMember } from '@/entities'
import MemberTag from '@/features/members/MemberTag.vue'

/**
 * Member list row. Compact viewports show inline rename and remove buttons; split layouts
 * make the full row selectable to inspect the member in the right detail pane.
 */
defineProps<{
  member: TripMember
  isMe: boolean
  isHolder: boolean
  canEdit: boolean
  split: boolean
  selected: boolean
}>()
defineEmits<{ rename: []; remove: []; select: [] }>()

const { t } = useI18n()
const iconButton =
  'flex size-11 shrink-0 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky'
</script>

<template>
  <li
    v-if="split"
    class="ink-border rounded-card"
    :class="selected ? 'bg-green-soft outline-green-ink outline-2 -outline-offset-2' : 'bg-surface'"
  >
    <button
      type="button"
      :aria-current="selected ? 'true' : undefined"
      class="flex min-h-12 w-full items-center px-3 py-1.5 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sky"
      @click="$emit('select')"
    >
      <MemberTag
        :member="member"
        :is-me="isMe"
        :is-holder="isHolder"
      />
    </button>
  </li>
  <li
    v-else
    class="flex min-h-11 items-center gap-2"
  >
    <MemberTag
      :member="member"
      :is-me="isMe"
      :is-holder="isHolder"
    />
    <template v-if="canEdit">
      <button
        type="button"
        :class="iconButton"
        :aria-label="t('members.renameOf', { name: member.display_name })"
        @click="$emit('rename')"
      >
        <Pencil
          :size="18"
          aria-hidden="true"
        />
      </button>
      <button
        v-if="!isMe"
        type="button"
        :class="[iconButton, 'text-danger']"
        :aria-label="t('members.removeOf', { name: member.display_name })"
        @click="$emit('remove')"
      >
        <UserMinus
          :size="18"
          aria-hidden="true"
        />
      </button>
    </template>
  </li>
</template>
