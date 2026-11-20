<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import type { TripSpendSummary } from '@/entities'
import CategoryBreakdown from '@/features/summary/CategoryBreakdown.vue'
import TotalCard from '@/features/summary/TotalCard.vue'
import type { CurrencyCode } from '@/lib/format'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{ summary: TripSpendSummary; currency: CurrencyCode }>()

const { t } = useI18n()
const money = useMoney(() => props.currency)
</script>

<template>
  <p
    v-if="summary.expense_count === 0"
    class="card-ink bg-sand p-4"
  >
    {{ t('trip.emptyTitle') }}
  </p>
  <div
    v-else
    class="flex flex-col gap-4"
  >
    <TotalCard
      :total="summary.total"
      :expense-count="summary.expense_count"
      :currency="currency"
    />
    <CategoryBreakdown
      :categories="summary.categories"
      :currency="currency"
    />
    <div class="grid grid-cols-2 gap-3">
      <BaseCard
        tone="yellow"
        class="flex flex-col gap-0.5"
      >
        <p class="text-sm">
          {{ t('summary.perPerson') }}
        </p>
        <p class="font-heading text-xl font-semibold break-words tabular-nums">
          {{ t('summary.approx', { amount: money(summary.per_person) }) }}
        </p>
      </BaseCard>
      <BaseCard
        tone="sky"
        class="flex flex-col gap-0.5"
      >
        <p class="text-sm">
          {{ t('summary.perDay') }}
        </p>
        <p class="font-heading text-xl font-semibold break-words tabular-nums">
          {{ t('summary.approx', { amount: money(summary.per_day) }) }}
        </p>
      </BaseCard>
    </div>
  </div>
</template>
