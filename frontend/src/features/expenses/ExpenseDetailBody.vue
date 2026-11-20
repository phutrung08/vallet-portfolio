<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MapPin, StickyNote } from 'lucide-vue-next'
import BaseCard from '@/components/BaseCard.vue'
import type { Expense, TripDetail } from '@/entities'
import ExpenseShareList from '@/features/expenses/ExpenseShareList.vue'
import { categoryIcons } from '@/features/expenses/categoryIcons'
import { mapsUrl, payerName } from '@/features/expenses/expenseFacts'
import { formatDayMonth, formatMoney } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

/** Expense summary card, participant share breakdown, optional note/place, and audit trail. */
const props = defineProps<{ trip: TripDetail; expense: Expense }>()

const { t, locale } = useI18n()
const appLocale = computed(() => locale.value as AppLocale)
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
</script>

<template>
  <BaseCard class="flex flex-col gap-2 p-4">
    <p class="font-heading text-4xl font-semibold tabular-nums">
      {{ formatMoney(expense.amount, trip.currency, appLocale) }}
    </p>
    <p class="flex items-center gap-2 text-sm">
      <component
        :is="categoryIcons[expense.category]"
        :size="16"
        aria-hidden="true"
      />
      {{ t(`expenseForm.categories.${expense.category}`) }} · {{ formatDayMonth(expense.spent_on, appLocale) }}
    </p>
    <p class="text-sm">
      {{ t('expenseForm.payer') }}: {{ payerName(expense, trip.members) ?? t('expense.fundName') }}
      · {{ t(`expense.split.${expense.split_mode}`) }}
    </p>
  </BaseCard>
  <ExpenseShareList
    :trip="trip"
    :expense="expense"
  />
  <p
    v-if="expense.note"
    class="flex gap-2 text-sm whitespace-pre-wrap break-words"
  >
    <StickyNote
      :size="16"
      class="text-muted mt-0.5 shrink-0"
      aria-hidden="true"
    />{{ expense.note }}
  </p>
  <a
    v-if="expense.place"
    :href="mapsUrl(expense.place)"
    target="_blank"
    rel="noopener noreferrer"
    class="flex min-h-11 items-center gap-2 text-sm break-words underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
  >
    <MapPin
      :size="16"
      class="text-muted shrink-0"
      aria-hidden="true"
    />{{ expense.place }}
  </a>
  <p class="text-muted text-xs">
    {{ t('expense.createdBy', { name: nameOf(expense.created_by) }) }}<template v-if="expense.updated_by">
      · {{ t('expense.editedBy', { name: nameOf(expense.updated_by) }) }}
    </template>
  </p>
</template>
