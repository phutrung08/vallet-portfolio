<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import BaseButton from '@/components/BaseButton.vue'
import type { DaySummary, Expense, TripDetail } from '@/entities'
import DayTabs from '@/features/expenses/DayTabs.vue'
import ExpenseList from '@/features/expenses/ExpenseList.vue'
import { defaultDay } from '@/features/expenses/dayTabs'
import { useAddExpense } from '@/features/expenses/useAddExpense'
import { localIsoDate } from '@/features/trips/tripMeta'
import { formatDayMonth, formatMoney } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

const props = withDefaults(
  defineProps<{
    trip: TripDetail
    days: readonly DaySummary[]
    today?: string
    split?: boolean
    selectedId?: string | null
  }>(),
  { today: () => localIsoDate(new Date()), split: false, selectedId: null },
)

const emit = defineEmits<{
  delete: [expense: Expense]
  select: [expense: Expense]
  shown: [expenses: readonly Expense[]]
}>()

const PANEL_ID = 'day-panel'
const { t, locale } = useI18n()
const addExpense = useAddExpense(() => props.trip.id)
// Honors `?day=` when returning from saving or editing an expense.
const route = useRoute()
const picked = ref<string | null>(typeof route.query.day === 'string' ? route.query.day : null)
watch(
  () => route.query.day,
  (day) => {
    if (typeof day === 'string') picked.value = day
  },
)
const selected = computed(() => {
  const chosen = props.days.find((day) => day.date === picked.value)
  return chosen?.date ?? defaultDay(props.days, props.today)
})
const current = computed(() => props.days.find((day) => day.date === selected.value))
const list = useTemplateRef('list')

/** Drops cached expenses for `date` so that day re-fetches from the API. */
async function invalidate(date: string): Promise<void> {
  await list.value?.invalidate(date)
}

/** Reloads the currently visible day and clears all cached other days. */
async function refreshDays(): Promise<void> {
  await list.value?.refreshAll()
}
defineExpose({ invalidate, refreshDays })
</script>

<template>
  <section
    v-if="days.length > 0"
    class="flex flex-col gap-2"
  >
    <DayTabs
      :days="days"
      :starts-on="trip.starts_on"
      :selected="selected"
      :panel-id="PANEL_ID"
      @select="picked = $event"
    />
    <div
      v-if="current"
      :id="PANEL_ID"
      role="tabpanel"
      :aria-labelledby="`day-tab-${current.date}`"
      class="flex flex-col gap-3"
    >
      <p class="flex items-baseline justify-between gap-3 text-sm">
        <span>
          {{ formatDayMonth(current.date, locale as AppLocale) }} ·
          {{ t('trip.expenseCount', current.count) }}
        </span>
        <span class="font-medium tabular-nums">
          {{ formatMoney(current.total, trip.currency, locale as AppLocale) }}
        </span>
      </p>
      <ExpenseList
        ref="list"
        :trip="trip"
        :day="current.date"
        :split="split"
        :selected-id="selectedId"
        @delete="emit('delete', $event)"
        @select="emit('select', $event)"
        @shown="emit('shown', $event)"
      />
    </div>
  </section>
  <section
    v-else
    class="card-ink bg-surface flex flex-col items-center gap-3 p-6 text-center"
  >
    <p class="font-heading text-lg">
      {{ t('trip.emptyTitle') }}
    </p>
    <BaseButton
      variant="primary"
      @click="addExpense"
    >
      {{ t('nav.add') }}
    </BaseButton>
  </section>
</template>
