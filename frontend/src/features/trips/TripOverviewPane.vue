<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRight } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import BaseCard from '@/components/BaseCard.vue'
import BasePill from '@/components/BasePill.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import type { TripSummary } from '@/entities'
import MeCard from '@/features/balances/MeCard.vue'
import OverviewExpenses from '@/features/trips/OverviewExpenses.vue'
import { dateRangeLabel, tripPhase } from '@/features/trips/tripMeta'
import { useTripOverview } from '@/features/trips/useTripOverview'
import { errorMessageKey } from '@/lib/errors'
import type { AppLocale } from '@/lib/i18n'
import { useMoney } from '@/lib/useMoney'

/**
 * Right pane of the split home screen showing the selected trip at a glance. Mounted keyed
 * by `trip.id` so overview requests run cleanly when selection changes.
 */
const props = defineProps<{ trip: TripSummary; today: string }>()
defineEmits<{ open: [] }>()

const { t, locale } = useI18n()
const overview = useTripOverview(() => props.trip.id, () => props.trip.me)
const money = useMoney(() => props.trip.currency)
const phase = computed(() => tripPhase(props.trip, props.today))
const meta = computed(() =>
  [dateRangeLabel(props.trip, locale.value as AppLocale), t('trips.members', props.trip.member_count)]
    .filter((part) => part !== '')
    .join(' · '),
)
const pillTone = { closed: 'neutral', upcoming: 'sky', ongoing: 'yellow' } as const
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex flex-col gap-1">
      <div class="flex items-start justify-between gap-3">
        <h2 class="min-w-0 text-2xl break-words">
          {{ trip.name }}
        </h2>
        <BasePill :tone="pillTone[phase]">
          {{ t(`trips.status.${phase}`) }}
        </BasePill>
      </div>
      <p class="text-sm">
        {{ meta }}
      </p>
    </div>

    <BaseButton
      variant="primary"
      block
      @click="$emit('open')"
    >
      {{ t('home.overview.open') }}
      <ArrowRight
        :size="18"
        class="ml-1.5"
        aria-hidden="true"
      />
    </BaseButton>

    <div
      v-if="overview.status.value === 'loading'"
      aria-busy="true"
      class="flex flex-col gap-4"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
      <div
        v-for="n in 2"
        :key="n"
        class="card-ink bg-sand h-24 animate-pulse motion-reduce:animate-none"
      />
    </div>
    <ErrorNotice
      v-else-if="overview.status.value === 'error'"
      :message="t(errorMessageKey(overview.error.value))"
      @retry="overview.reload"
    />
    <template v-else>
      <BaseCard class="flex flex-col gap-1 p-4">
        <p class="text-sm font-medium">
          {{ t('trip.spentLabel') }}
        </p>
        <p class="font-heading text-4xl leading-none font-semibold break-words tabular-nums">
          {{ money(overview.spentTotal.value) }}
        </p>
      </BaseCard>
      <MeCard
        v-if="overview.mine.value"
        :standing="overview.mine.value"
        :currency="trip.currency"
      />
      <OverviewExpenses
        :expenses="overview.recent.value"
        :currency="trip.currency"
      />
    </template>
  </div>
</template>
