<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRight, Trash2 } from 'lucide-vue-next'
import type { Payment, TripDetail } from '@/entities'
import PersonName from '@/features/balances/PersonName.vue'
import { newestPaymentsFirst } from '@/features/balances/balanceRules'
import { formatDayMonth } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{
  trip: TripDetail
  payments: readonly Payment[]
  canDelete: boolean
}>()
defineEmits<{ delete: [payment: Payment] }>()

const { t, locale } = useI18n()
const money = useMoney(() => props.trip.currency)
const rows = computed(() => newestPaymentsFirst(props.payments))
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
const dayOf = (isoDate: string) => formatDayMonth(isoDate, locale.value as AppLocale)
</script>

<template>
  <section
    v-if="rows.length > 0"
    class="flex flex-col gap-2"
  >
    <h2 class="text-lg">
      {{ t('balances.paidTitle') }}
    </h2>
    <ul class="flex flex-col gap-1">
      <li
        v-for="item in rows"
        :key="item.id"
        class="flex min-h-11 items-center gap-3"
      >
        <span class="min-w-0 flex-1">
          <span class="flex flex-wrap items-center gap-x-1.5">
            <PersonName
              :trip="trip"
              :member-id="item.payer"
            />
            <ArrowRight
              :size="14"
              class="shrink-0"
              aria-hidden="true"
            />
            <span class="sr-only">{{ t('balances.pays') }}</span>
            <PersonName
              :trip="trip"
              :member-id="item.payee"
            />
          </span>
          <span class="text-muted block text-xs">{{ dayOf(item.paid_on) }}</span>
        </span>
        <span class="font-medium tabular-nums">{{ money(item.amount) }}</span>
        <button
          v-if="canDelete"
          type="button"
          :aria-label="t('balances.deleteLabel', { payer: nameOf(item.payer), payee: nameOf(item.payee) })"
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
