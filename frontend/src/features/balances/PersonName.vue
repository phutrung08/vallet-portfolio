<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TripDetail } from '@/entities'

const props = defineProps<{ trip: Pick<TripDetail, 'members'>; memberId: string }>()

const { t } = useI18n()
const member = computed(() => props.trip.members.find((item) => item.id === props.memberId))
</script>

<template>
  <span class="break-words">
    {{ member?.display_name }}
    <span
      v-if="member?.removed"
      class="text-muted text-xs"
    >{{ t('balances.left') }}</span>
  </span>
</template>
