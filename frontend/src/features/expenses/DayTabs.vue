<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BasePill from '@/components/BasePill.vue'
import type { DaySummary } from '@/entities'
import { tripDayNumber } from '@/features/expenses/dayTabs'
import { useDayTabs } from '@/features/expenses/useDayTabs'
import { formatDayMonth } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

const props = defineProps<{
  days: readonly DaySummary[]
  startsOn: string | null
  selected: string | null
  panelId: string
}>()
const emit = defineEmits<{ select: [date: string] }>()

const { t, locale } = useI18n()

function label(date: string): string {
  const number = tripDayNumber(date, props.startsOn)
  return number === null
    ? formatDayMonth(date, locale.value as AppLocale)
    : t('trip.dayNumber', { n: number })
}

const { list, onKeydown } = useDayTabs(
  () => props.days,
  () => props.selected,
  (date) => emit('select', date),
)
</script>

<template>
  <div
    ref="list"
    role="tablist"
    :aria-label="t('trip.days')"
    class="-mx-4 flex gap-1 overflow-x-auto px-4"
  >
    <button
      v-for="(day, index) in days"
      :id="`day-tab-${day.date}`"
      :key="day.date"
      type="button"
      role="tab"
      :aria-selected="day.date === selected"
      :aria-controls="panelId"
      :tabindex="day.date === selected ? 0 : -1"
      class="flex min-h-11 shrink-0 items-center rounded-full px-0.5 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-sky"
      @click="emit('select', day.date)"
      @keydown="onKeydown($event, index)"
    >
      <BasePill
        :selected="day.date === selected"
        class="px-3 py-1.5 text-sm"
      >
        {{ label(day.date) }}
      </BasePill>
    </button>
  </div>
</template>
