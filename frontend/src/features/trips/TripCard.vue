<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import BaseCard from '@/components/BaseCard.vue'
import BasePill from '@/components/BasePill.vue'
import type { TripSummary } from '@/entities'
import { dateRangeLabel, includesToday, tripPhase } from '@/features/trips/tripMeta'
import type { AppLocale } from '@/lib/i18n'

/**
 * Renders as a RouterLink on mobile, or a selection button on split screens where
 * clicking the selected trip opens it.
 */
const props = defineProps<{ trip: TripSummary; today: string; split?: boolean; selected?: boolean }>()
defineEmits<{ select: [] }>()

const { t, locale } = useI18n()

const phase = computed(() => tripPhase(props.trip, props.today))
const dates = computed(() => dateRangeLabel(props.trip, locale.value as AppLocale))
const tone = computed(() => {
  if (phase.value === 'closed') return 'sand'
  return phase.value === 'ongoing' && includesToday(props.trip, props.today) ? 'green' : 'surface'
})
const pillTone = { closed: 'neutral', upcoming: 'sky', ongoing: 'yellow' } as const
</script>

<template>
  <component
    :is="split ? 'button' : RouterLink"
    v-bind="split ? { type: 'button', 'aria-current': selected ? 'true' : undefined } : { to: `/trips/${trip.id}` }"
    class="block w-full rounded-card text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
    :class="selected && 'outline-green-ink outline-2 outline-offset-2'"
    @click="split && $emit('select')"
  >
    <BaseCard
      :tone="tone"
      :flat="phase === 'closed'"
      class="flex min-h-11 flex-col gap-2 p-4"
    >
      <div class="flex items-start justify-between gap-3">
        <h2 class="min-w-0 text-lg break-words">
          {{ trip.name }}
        </h2>
        <BasePill :tone="pillTone[phase]">
          {{ t(`trips.status.${phase}`) }}
        </BasePill>
      </div>
      <p class="text-sm">
        <span v-if="dates">{{ dates }} · </span>{{ t('trips.members', trip.member_count) }}
      </p>
    </BaseCard>
  </component>
</template>
