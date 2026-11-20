<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseAvatar from '@/components/BaseAvatar.vue'
import type { Expense, ExpenseShare, TripDetail } from '@/entities'
import { formatBasisPoints, formatMoney } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

/** Renders each expense share with member avatar, weight label (when relevant), and amount. */
const props = defineProps<{ trip: TripDetail; expense: Expense }>()

const { t, locale } = useI18n()
const appLocale = computed(() => locale.value as AppLocale)
const rows = computed(() =>
  props.expense.shares.map((share) => {
    const member = props.trip.members.find((candidate) => candidate.id === share.member_id)
    const name = member?.display_name ?? ''
    return { share, name, label: member?.removed ? t('expenseForm.left', { name }) : name }
  }),
)

function weightLabel(share: ExpenseShare): string | null {
  if (props.expense.split_mode === 'shares') return t('expense.shareCount', share.weight)
  return props.expense.split_mode === 'percent' ? formatBasisPoints(share.weight, appLocale.value) : null
}
</script>

<template>
  <ul class="flex flex-col gap-2">
    <li
      v-for="row in rows"
      :key="row.share.member_id"
      class="flex items-center gap-3"
    >
      <BaseAvatar :name="row.name" />
      <span class="min-w-0 flex-1 break-words">{{ row.label }}</span>
      <span
        v-if="weightLabel(row.share)"
        class="text-muted text-sm"
      >{{ weightLabel(row.share) }}</span>
      <span class="font-medium tabular-nums">
        {{ formatMoney(row.share.amount, trip.currency, appLocale) }}
      </span>
    </li>
  </ul>
</template>
