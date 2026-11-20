<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ErrorNotice from '@/components/ErrorNotice.vue'
import type { Expense, TripDetail } from '@/entities'
import ExpenseRow from '@/features/expenses/ExpenseRow.vue'
import { useDayExpenses } from '@/features/expenses/useDayExpenses'
import { errorMessageKey } from '@/lib/errors'
import { useTripSource } from '@/lib/tripSource'

const props = defineProps<{ trip: TripDetail; day: string; split?: boolean; selectedId?: string | null }>()
const emit = defineEmits<{
  delete: [expense: Expense]
  select: [expense: Expense]
  shown: [expenses: readonly Expense[]]
}>()

const { t } = useI18n()
const { expenses, status, error, reload, invalidate, refreshAll } = useDayExpenses(
  () => props.trip.id,
  () => props.day,
  useTripSource().read,
)
const openId = ref<string | null>(null)
defineExpose({ invalidate, refreshAll })

// Notifies parent container when expenses finish loading so default split selection updates.
watch(
  [status, expenses],
  () => {
    if (status.value === 'ready') emit('shown', expenses.value)
  },
  { immediate: true },
)
watch(
  () => props.day,
  () => {
    openId.value = null
  },
)
</script>

<template>
  <div
    v-if="status === 'loading'"
    aria-busy="true"
    class="flex flex-col gap-2"
  >
    <span class="sr-only">{{ t('common.loading') }}</span>
    <div
      v-for="n in 3"
      :key="n"
      class="ink-border rounded-card bg-sand h-14 animate-pulse motion-reduce:animate-none"
    />
  </div>
  <ErrorNotice
    v-else-if="status === 'error'"
    :message="t(errorMessageKey(error))"
    @retry="reload"
  />
  <ul
    v-else
    class="flex flex-col gap-2"
  >
    <ExpenseRow
      v-for="expense in expenses"
      :key="expense.id"
      :trip="trip"
      :expense="expense"
      :open="openId === expense.id"
      :split="split"
      :selected="split && selectedId === expense.id"
      @select="emit('select', expense)"
      @toggle="openId = openId === expense.id ? null : expense.id"
      @delete="emit('delete', expense)"
    />
  </ul>
</template>
