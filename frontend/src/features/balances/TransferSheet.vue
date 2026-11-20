<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BottomSheet from '@/components/BottomSheet.vue'
import type { BankAccount, Transfer, TripDetail } from '@/entities'
import TransferPanel from '@/features/balances/TransferPanel.vue'

const props = defineProps<{
  trip: TripDetail
  /** The transfer being paid; the sheet is open while there is one. */
  transfer: Transfer | null
  accounts: readonly BankAccount[]
  onRecorded: () => Promise<void>
}>()
defineEmits<{ close: []; addAccount: [] }>()

const { t } = useI18n()
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
const title = computed(() =>
  props.transfer
    ? t('balances.qr.title', { payer: nameOf(props.transfer.payer), payee: nameOf(props.transfer.payee) })
    : '',
)
</script>

<template>
  <BottomSheet
    :open="transfer !== null"
    :title="title"
    @close="$emit('close')"
  >
    <TransferPanel
      v-if="transfer"
      :trip="trip"
      :transfer="transfer"
      :accounts="accounts"
      :on-recorded="onRecorded"
      @add-account="$emit('addAccount')"
    />
  </BottomSheet>
</template>
