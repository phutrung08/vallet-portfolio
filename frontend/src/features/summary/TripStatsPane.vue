<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ErrorNotice from '@/components/ErrorNotice.vue'
import type { TripDetail } from '@/entities'
import CategoryBreakdown from '@/features/summary/CategoryBreakdown.vue'
import PaidBreakdown from '@/features/summary/PaidBreakdown.vue'
import TotalCard from '@/features/summary/TotalCard.vue'
import { useTripStats } from '@/features/summary/useTripStats'
import { ApiError } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'

/** Renders the split-view Stats mode: spend totals, category distribution, and payer breakdown. */
const props = defineProps<{ trip: TripDetail }>()

const { t } = useI18n()
const { data, status, error, reload } = useTripStats(() => props.trip)
</script>

<template>
  <section class="flex flex-1 flex-col gap-4">
    <div
      v-if="status === 'loading'"
      aria-busy="true"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
      <div class="card-ink bg-sand h-48 animate-pulse motion-reduce:animate-none" />
    </div>
    <ErrorNotice
      v-else-if="status === 'error'"
      :message="t(errorMessageKey(error))"
      :can-retry="!(error instanceof ApiError && error.code === 'not_found')"
      @retry="reload"
    />
    <template v-else-if="data">
      <TotalCard
        :total="data.summary.total"
        :expense-count="data.summary.expense_count"
        :currency="trip.currency"
      />
      <CategoryBreakdown
        v-if="data.summary.categories.length > 0"
        :categories="data.summary.categories"
        :currency="trip.currency"
      />
      <PaidBreakdown
        :trip="trip"
        :standings="data.standings"
      />
    </template>
  </section>
</template>
