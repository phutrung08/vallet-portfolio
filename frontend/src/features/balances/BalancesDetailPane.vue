<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Eye, PartyPopper } from 'lucide-vue-next'
import BaseCard from '@/components/BaseCard.vue'
import type { BankAccount, Transfer, TripDetail } from '@/entities'
import SummaryLink from '@/features/balances/SummaryLink.vue'
import TransferPanel from '@/features/balances/TransferPanel.vue'
import { transferKey } from '@/features/balances/useTransferSelection'
import { useTripSource } from '@/lib/tripSource'

/**
 * The right pane of the balances screen on split layouts: the selected transfer with its
 * amount, QR code, and "paid" action, or a settled note with the trip summary link.
 */
const props = defineProps<{
  trip: TripDetail
  transfers: readonly Transfer[]
  selected: Transfer | null
  accounts: readonly BankAccount[]
  editable: boolean
  onRecorded: () => Promise<void>
}>()
defineEmits<{ addAccount: [] }>()

const { t } = useI18n()
const { readonly } = useTripSource()
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
const title = computed(() =>
  props.selected
    ? t('balances.qr.title', { payer: nameOf(props.selected.payer), payee: nameOf(props.selected.payee) })
    : '',
)
</script>

<template>
  <template v-if="selected && editable">
    <h2 class="text-lg break-words">
      {{ title }}
    </h2>
    <!-- A partial payment changes the amount, which starts the panel afresh. -->
    <TransferPanel
      :key="`${transferKey(selected)}:${selected.amount}`"
      :trip="trip"
      :transfer="selected"
      :accounts="accounts"
      :on-recorded="onRecorded"
      @add-account="$emit('addAccount')"
    />
  </template>
  <div
    v-else
    class="flex flex-1 items-center justify-center"
  >
    <BaseCard
      :tone="transfers.length === 0 ? 'yellow' : 'surface'"
      class="flex max-w-xs flex-col items-center gap-3 p-6 text-center"
    >
      <PartyPopper
        v-if="transfers.length === 0"
        :size="32"
        aria-hidden="true"
      />
      <Eye
        v-else
        :size="32"
        class="text-muted"
        aria-hidden="true"
      />
      <p
        v-if="transfers.length === 0"
        class="font-heading text-xl font-semibold"
      >
        {{ t('balances.empty') }}
      </p>
      <p
        v-else
        class="text-muted"
      >
        {{ t('balances.pane.readOnly') }}
      </p>
      <SummaryLink
        v-if="!readonly"
        :trip-id="trip.id"
      />
    </BaseCard>
  </div>
</template>
