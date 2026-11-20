<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { ChevronRight } from 'lucide-vue-next'
import BaseCard from '@/components/BaseCard.vue'
import BasePill from '@/components/BasePill.vue'
import type { FundSummary, TripDetail } from '@/entities'
import { activeMemberCount, dateRangeLabel, spentPercent } from '@/features/trips/tripMeta'
import { formatMoney } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'
import { useTripSource } from '@/lib/tripSource'

const props = defineProps<{ trip: TripDetail; fund: FundSummary | null; spentTotal: number }>()

const { t, locale } = useI18n()
const { readonly } = useTripSource()

const money = (minor: number) => formatMoney(minor, props.trip.currency, locale.value as AppLocale)
const meta = computed(() =>
  [
    dateRangeLabel(props.trip, locale.value as AppLocale),
    t('trips.members', activeMemberCount(props.trip)),
  ]
    .filter((part) => part !== '')
    .join(' · '),
)
const percent = computed(() => (props.fund ? spentPercent(props.fund.contributed, props.fund.spent) : 0))
const overdrawn = computed(() => props.fund !== null && props.fund.remaining < 0)
</script>

<template>
  <BaseCard
    tone="green"
    class="flex flex-col gap-1 p-4"
  >
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm">
        {{ meta }}
      </p>
      <RouterLink
        v-if="fund && !readonly"
        :to="`/trips/${trip.id}/fund`"
        class="-my-2 -mr-2 inline-flex min-h-11 items-center px-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      >
        {{ t('trip.fundLink') }}
        <ChevronRight
          :size="16"
          aria-hidden="true"
        />
      </RouterLink>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <p class="text-sm font-medium">
        {{ fund ? t('trip.fundRemaining') : t('trip.spentLabel') }}
      </p>
      <BasePill
        v-if="trip.closed"
        tone="yellow"
      >
        {{ t('trips.status.closed') }}
      </BasePill>
      <BasePill
        v-if="trip.locked"
        tone="sky"
      >
        {{ t('trip.locked') }}
      </BasePill>
      <BasePill
        v-if="overdrawn"
        tone="danger"
      >
        {{ t('trip.fundNegative') }}
      </BasePill>
    </div>
    <p class="font-heading text-4xl leading-none font-semibold break-words tabular-nums">
      {{ money(fund ? fund.remaining : spentTotal) }}
    </p>
    <template v-if="fund">
      <div
        role="progressbar"
        :aria-label="t('trip.progress', { percent })"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuenow="percent"
        class="bg-green-dark mt-2 h-2.5 overflow-hidden rounded-full"
      >
        <div
          class="bg-yellow h-full rounded-full"
          :style="{ width: `${percent}%` }"
        />
      </div>
      <p class="text-sm tabular-nums">
        {{ t('trip.contributed', { amount: money(fund.contributed) }) }} ·
        {{ t('trip.spent', { amount: money(fund.spent) }) }}
      </p>
    </template>
  </BaseCard>
</template>
