<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import type { Expense } from '@/entities'
import { categoryIcons } from '@/features/expenses/categoryIcons'
import type { CurrencyCode } from '@/lib/format'
import { useMoney } from '@/lib/useMoney'

/** Up to four recent expenses shown on the split home overview pane; full list lives on the trip page. */
const props = defineProps<{ expenses: Expense[]; currency: CurrencyCode }>()

const { t } = useI18n()
const money = useMoney(() => props.currency)
</script>

<template>
  <section class="flex flex-col gap-2">
    <h3 class="text-base">
      {{ t('home.overview.recent') }}
    </h3>
    <p
      v-if="expenses.length === 0"
      class="text-muted text-sm"
    >
      {{ t('home.overview.noExpenses') }}
    </p>
    <BaseCard
      v-else
      flat
      class="p-1"
    >
      <ul>
        <li
          v-for="expense in expenses"
          :key="expense.id"
          class="flex min-h-11 items-center gap-3 px-3 py-1.5"
        >
          <component
            :is="categoryIcons[expense.category]"
            :size="18"
            aria-hidden="true"
            class="shrink-0"
          />
          <span class="min-w-0 flex-1 text-sm break-words">{{ expense.title }}</span>
          <span class="text-sm font-medium whitespace-nowrap tabular-nums">{{ money(expense.amount) }}</span>
        </li>
      </ul>
    </BaseCard>
  </section>
</template>
