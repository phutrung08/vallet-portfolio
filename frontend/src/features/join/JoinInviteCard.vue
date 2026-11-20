<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import type { JoinPreview } from '@/entities'
import { dateRangeLabel } from '@/features/trips/tripMeta'
import type { AppLocale } from '@/lib/i18n'

const props = defineProps<{ preview: JoinPreview }>()

const { t, locale } = useI18n()
const meta = computed(() =>
  [
    dateRangeLabel(props.preview.trip, locale.value as AppLocale),
    t('trips.members', props.preview.members.length),
  ]
    .filter((part) => part !== '')
    .join(' · '),
)
</script>

<template>
  <BaseCard
    tone="green"
    class="flex flex-col gap-1 p-4"
  >
    <p class="text-sm font-medium">
      {{ t('join.invited') }}
    </p>
    <h1 class="text-3xl leading-tight break-words">
      {{ preview.trip.name }}
    </h1>
    <p class="text-sm">
      {{ meta }}
    </p>
  </BaseCard>
</template>
