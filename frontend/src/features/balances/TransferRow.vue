<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRight, QrCode } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import type { Transfer, TripDetail } from '@/entities'
import PersonName from '@/features/balances/PersonName.vue'
import { useMoney } from '@/lib/useMoney'

/**
 * Settlement suggestion row. Compact screens show a QR trigger button; split screens turn
 * the entire row into a selectable item driving the detail pane.
 */
const props = defineProps<{
  trip: TripDetail
  transfer: Transfer
  canPay: boolean
  split: boolean
  selected: boolean
}>()
defineEmits<{ pay: [] }>()

const { t } = useI18n()
const money = useMoney(() => props.trip.currency)
const picking = computed(() => props.split && props.canPay)
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
const label = computed(() =>
  t('balances.qr.open', { payer: nameOf(props.transfer.payer), payee: nameOf(props.transfer.payee) }),
)
</script>

<template>
  <li>
    <component
      :is="picking ? 'button' : 'div'"
      :type="picking ? 'button' : undefined"
      :aria-current="picking && selected ? 'true' : undefined"
      :aria-label="picking ? label : undefined"
      class="ink-border rounded-card flex min-h-12 w-full items-center gap-2 px-3 py-1.5 text-left"
      :class="[
        selected && picking ? 'bg-green-soft outline-green-ink outline-2 -outline-offset-2' : 'bg-surface',
        picking && 'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sky',
      ]"
      @click="picking && $emit('pay')"
    >
      <span class="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5">
        <PersonName
          :trip="trip"
          :member-id="transfer.payer"
          class="font-medium"
        />
        <ArrowRight
          :size="16"
          class="shrink-0"
          aria-hidden="true"
        />
        <span class="sr-only">{{ t('balances.pays') }}</span>
        <PersonName
          :trip="trip"
          :member-id="transfer.payee"
          class="font-medium"
        />
      </span>
      <span class="font-medium tabular-nums">{{ money(transfer.amount) }}</span>
      <BaseButton
        v-if="canPay && !split"
        variant="dark"
        class="shrink-0 px-3"
        :aria-label="label"
        @click="$emit('pay')"
      >
        <QrCode
          :size="16"
          class="mr-1"
          aria-hidden="true"
        />
        {{ t('balances.qr.button') }}
      </BaseButton>
    </component>
  </li>
</template>
