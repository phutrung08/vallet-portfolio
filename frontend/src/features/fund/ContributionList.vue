<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Trash2 } from 'lucide-vue-next'
import type { Contribution, TripDetail } from '@/entities'
import { newestFirst } from '@/features/fund/fundRules'
import { formatDayMonth } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{
  trip: TripDetail
  contributions: readonly Contribution[]
  canDelete: boolean
}>()
defineEmits<{ delete: [contribution: Contribution] }>()

const { t, locale } = useI18n()
const money = useMoney(() => props.trip.currency)
const rows = computed(() => newestFirst(props.contributions))
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
const dayOf = (isoDate: string) => formatDayMonth(isoDate, locale.value as AppLocale)
</script>

<template>
  <section class="flex flex-col gap-2">
    <h2 class="text-lg">
      {{ t('fund.historyTitle') }}
    </h2>
    <p
      v-if="rows.length === 0"
      class="text-muted text-sm"
    >
      {{ t('fund.historyEmpty') }}
    </p>
    <ul
      v-else
      class="flex flex-col gap-1"
    >
      <li
        v-for="item in rows"
        :key="item.id"
        class="flex min-h-11 items-center gap-3"
      >
        <span class="min-w-0 flex-1">
          <span class="block break-words">{{ nameOf(item.member_id) }}</span>
          <span class="text-muted block text-xs">{{ dayOf(item.contributed_on) }}</span>
        </span>
        <span class="font-medium tabular-nums">{{ money(item.amount) }}</span>
        <button
          v-if="canDelete"
          type="button"
          :aria-label="t('fund.deleteLabel', { name: nameOf(item.member_id) })"
          class="text-danger flex size-11 shrink-0 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
          @click="$emit('delete', item)"
        >
          <Trash2
            :size="18"
            aria-hidden="true"
          />
        </button>
      </li>
    </ul>
  </section>
</template>
