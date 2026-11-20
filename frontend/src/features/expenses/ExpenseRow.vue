<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown } from 'lucide-vue-next'
import type { Expense, TripDetail } from '@/entities'
import ExpenseRowPanel from '@/features/expenses/ExpenseRowPanel.vue'
import { categoryIcons } from '@/features/expenses/categoryIcons'
import { activeMembers, participantCount, payerName } from '@/features/expenses/expenseFacts'
import { formatMoney } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

/**
 * Collapsible expense row on compact screens; selectable list item on split layouts.
 */
const props = defineProps<{
  trip: TripDetail
  expense: Expense
  open: boolean
  split?: boolean
  selected?: boolean
}>()
defineEmits<{ toggle: []; select: []; delete: [] }>()

const { t, locale } = useI18n()
const panelId = computed(() => `expense-panel-${props.expense.id}`)
const amount = computed(() => formatMoney(props.expense.amount, props.trip.currency, locale.value as AppLocale))
const subtitle = computed(() =>
  t('expense.subtitle', {
    name: payerName(props.expense, props.trip.members) ?? t('expense.fundName'),
    x: participantCount(props.expense),
    y: activeMembers(props.trip.members).length,
  }),
)
</script>

<template>
  <li
    class="ink-border rounded-card overflow-hidden"
    :class="selected ? 'bg-green-soft outline-green-ink outline-2 -outline-offset-2' : 'bg-surface'"
  >
    <button
      type="button"
      :aria-expanded="split ? undefined : open"
      :aria-controls="split ? undefined : panelId"
      :aria-current="split && selected ? 'true' : undefined"
      class="flex min-h-14 w-full items-center gap-3 p-3 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sky"
      @click="split ? $emit('select') : $emit('toggle')"
    >
      <span class="bg-sand flex size-9 shrink-0 items-center justify-center rounded-full">
        <component
          :is="categoryIcons[expense.category]"
          :size="18"
          aria-hidden="true"
        />
      </span>
      <span class="min-w-0 flex-1">
        <span
          class="block font-medium"
          :class="split ? 'line-clamp-2 break-words' : 'truncate'"
        >{{ expense.title }}</span>
        <span
          v-if="split"
          class="block font-medium tabular-nums"
        >{{ amount }}</span>
        <span class="text-muted block truncate text-sm">{{ subtitle }}</span>
      </span>
      <span
        v-if="!split"
        class="font-medium tabular-nums"
      >{{ amount }}</span>
      <ChevronDown
        v-if="!split"
        :size="18"
        class="text-muted shrink-0 transition-transform motion-reduce:transition-none"
        :class="open && 'rotate-180'"
        aria-hidden="true"
      />
    </button>
    <ExpenseRowPanel
      v-if="open && !split"
      :id="panelId"
      :trip="trip"
      :expense="expense"
      @delete="$emit('delete')"
    />
  </li>
</template>
