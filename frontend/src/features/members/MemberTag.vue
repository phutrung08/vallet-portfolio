<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseAvatar from '@/components/BaseAvatar.vue'
import BasePill from '@/components/BasePill.vue'
import type { TripMember } from '@/entities'

withDefaults(
  defineProps<{ member: TripMember; isMe: boolean; isHolder: boolean; nameTag?: 'span' | 'h2' }>(),
  { nameTag: 'span' },
)

const { t } = useI18n()
</script>

<template>
  <span class="flex min-w-0 flex-1 items-center gap-2">
    <BaseAvatar :name="member.display_name" />
    <component
      :is="nameTag"
      class="min-w-0 flex-1 break-words"
      :class="nameTag === 'h2' && 'text-xl'"
    >
      {{ member.display_name }}
    </component>
    <BasePill
      v-if="isMe"
      tone="green"
    >
      {{ t('members.you') }}
    </BasePill>
    <BasePill
      v-if="isHolder"
      tone="yellow"
    >
      {{ t('members.holder') }}
    </BasePill>
  </span>
</template>
