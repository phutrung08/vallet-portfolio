<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseAvatar from '@/components/BaseAvatar.vue'
import BaseCard from '@/components/BaseCard.vue'
import type { TripDetail, TripSpendSummary } from '@/entities'
import PersonName from '@/features/balances/PersonName.vue'
import CategoryBreakdown from '@/features/summary/CategoryBreakdown.vue'
import TotalCard from '@/features/summary/TotalCard.vue'
import { percentsOf } from '@/features/summary/summaryRules'
import type { CurrencyCode } from '@/lib/format'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{ trip: TripDetail; summary: TripSpendSummary; currency: CurrencyCode }>()

const { t } = useI18n()
const money = useMoney(() => props.currency)
const payerRows = computed(() => {
  const sorted = [...props.summary.payers].sort((a, b) => b.amount - a.amount)
  const percents = percentsOf(sorted.map((payer) => payer.amount))
  return sorted.map((payer, index) => ({ payer, percent: percents[index] ?? 0 }))
})
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
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
    <BaseCard
      v-if="payerRows.length"
      class="flex flex-col gap-3 p-4"
      as="section"
    >
      <h2 class="text-lg">
        {{ t('stats.paidBy') }}
      </h2>
      <ul class="flex flex-col gap-3">
        <li
          v-for="{ payer, percent } in payerRows"
          :key="payer.paid_by ?? 'fund'"
          class="flex items-start gap-3"
        >
          <BaseAvatar
            :name="payer.paid_by ? nameOf(payer.paid_by) : t('expense.fundName')"
            class="mt-0.5"
          />
          <div class="min-w-0 flex-1">
            <div class="flex items-baseline justify-between gap-2">
              <PersonName
                v-if="payer.paid_by"
                :trip="trip"
                :member-id="payer.paid_by"
                class="min-w-0 font-medium"
              />
              <span
                v-else
                class="min-w-0 font-medium"
              >
                {{ t('expense.fundName') }}
              </span>
              <span class="font-medium tabular-nums">{{ money(payer.amount) }}</span>
            </div>
            <div
              role="img"
              :aria-label="t('summary.percent', { n: percent })"
              class="ink-border mt-1 h-3 overflow-hidden rounded-full"
            >
              <div
                class="bg-green h-full"
                :style="{ width: `${percent}%` }"
              />
            </div>
            <p class="text-muted mt-0.5 text-sm tabular-nums">
              {{ t('summary.expenseCount', { n: payer.count }) }}
            </p>
          </div>
        </li>
      </ul>
    </BaseCard>
  </div>
</template>
