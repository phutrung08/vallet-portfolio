<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ReceiptText } from 'lucide-vue-next'
import SegmentedControl from '@/components/SegmentedControl.vue'
import type { Expense, TripDetail } from '@/entities'
import ExpenseAddPane from '@/features/expenses/ExpenseAddPane.vue'
import ExpenseDetailPane from '@/features/expenses/ExpenseDetailPane.vue'
import { readOnlyKeyOf } from '@/features/expenses/expenseFacts'
import TripStatsPane from '@/features/summary/TripStatsPane.vue'
import { useTripPane, type PaneMode } from '@/features/trips/useTripPane'
import { useTripSource } from '@/lib/tripSource'

/**
 * Right pane of the split trip screen: switches between expense Details, inline Add (when
 * editable), and server-backed Stats, or shows a prompt when no expense exists yet.
 */
const props = defineProps<{ trip: TripDetail; selectedId: string | null; hasExpenses: boolean }>()
const emit = defineEmits<{ delete: [expense: Expense]; saved: [expense: Expense] }>()

const { t } = useI18n()
const source = useTripSource()
const canAdd = computed(() => !source.readonly && readOnlyKeyOf(props.trip) === null)
const { mode, setMode } = useTripPane(canAdd, computed(() => props.hasExpenses))
const options = computed<{ value: PaneMode; label: string }[]>(() => {
  const all: { value: PaneMode; label: string }[] = [
    { value: 'details', label: t('trip.pane.details') },
    { value: 'add', label: t('trip.pane.add') },
    { value: 'stats', label: t('trip.pane.stats') },
  ]
  return all.filter((option) => (option.value !== 'add' || canAdd.value) && (option.value !== 'stats' || props.hasExpenses))
})
</script>

<template>
  <SegmentedControl
    :model-value="mode"
    :label="t('trip.pane.label')"
    :options="options"
    @update:model-value="setMode"
  />
  <ExpenseAddPane
    v-if="mode === 'add'"
    :trip="trip"
    :closable="hasExpenses"
    @close="setMode('details')"
    @saved="emit('saved', $event)"
  />
  <TripStatsPane
    v-else-if="mode === 'stats'"
    :trip="trip"
  />
  <ExpenseDetailPane
    v-else-if="selectedId && hasExpenses"
    :trip="trip"
    :expense-id="selectedId"
    @delete="emit('delete', $event)"
    @saved="emit('saved', $event)"
  />
  <div
    v-else
    class="flex flex-1 items-center justify-center"
  >
    <div class="card-ink bg-surface flex max-w-xs flex-col items-center gap-3 p-6 text-center">
      <ReceiptText
        :size="32"
        class="text-muted"
        aria-hidden="true"
      />
      <p class="text-muted">
        {{ hasExpenses ? t('trip.pickExpense') : t('trip.noExpenseYet') }}
      </p>
    </div>
  </div>
</template>
