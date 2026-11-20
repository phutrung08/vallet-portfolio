<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import type { Balances, BankAccount, Payment, Transfer, TripDetail } from '@/entities'
import BalanceTabs, { type BalanceTab } from '@/features/balances/BalanceTabs.vue'
import CloseTripSection from '@/features/balances/CloseTripSection.vue'
import MeCard from '@/features/balances/MeCard.vue'
import MemberBalances from '@/features/balances/MemberBalances.vue'
import MyBankAccount from '@/features/balances/MyBankAccount.vue'
import PaymentHistory from '@/features/balances/PaymentHistory.vue'
import SummaryLink from '@/features/balances/SummaryLink.vue'
import TransferList from '@/features/balances/TransferList.vue'
import TransferSheet from '@/features/balances/TransferSheet.vue'
import { api } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useTripSource } from '@/lib/tripSource'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

const props = defineProps<{
  trip: TripDetail
  balances: Balances
  payments: readonly Payment[]
  accounts: readonly BankAccount[]
  /** Whether payments can be recorded: not on a locked trip or bundled demo. */
  editable: boolean
  split: boolean
  selectedKey: string | null
  refresh: () => Promise<void>
}>()
const emit = defineEmits<{ select: [transfer: Transfer]; editAccount: [] }>()

const { t } = useI18n()
const tab = ref<BalanceTab>('transfers')
const { readonly } = useTripSource()
const me = computed(() => props.balances.members.find((item) => item.member_id === props.trip.me))
const myAccount = computed(() => props.accounts.find((item) => item.member_id === props.trip.me) ?? null)
const paying = ref<Transfer | null>(null)
const removal = useConfirmedAction<Payment>(async (payment) => {
  const base = `/trips/${encodeURIComponent(props.trip.id)}/payments`
  await api.delete<void>(`${base}/${encodeURIComponent(payment.id)}`)
  await props.refresh()
})

async function recorded(): Promise<void> {
  await props.refresh()
  paying.value = null
}

// On a split layout the row selects the transfer for the detail pane; on phones it opens the sheet.
function pick(transfer: Transfer): void {
  if (props.split) emit('select', transfer)
  else paying.value = transfer
}

function addAccount(): void {
  paying.value = null
  emit('editAccount')
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <p
      v-if="trip.locked"
      class="card-ink bg-sand p-3 text-sm"
    >
      {{ t('errors.trip_locked') }}
    </p>
    <BalanceTabs v-model="tab" />
    <template v-if="tab === 'transfers'">
      <MeCard
        v-if="me"
        :standing="me"
        :currency="trip.currency"
      />
      <TransferList
        :trip="trip"
        :transfers="balances.transfers"
        :can-pay="editable"
        :split="split"
        :selected-key="selectedKey"
        @pay="pick"
      />
      <PaymentHistory
        :trip="trip"
        :payments="payments"
        :can-delete="editable"
        @delete="removal.ask"
      />
    </template>
    <MemberBalances
      v-else
      :trip="trip"
      :standings="balances.members"
      :has-payments="payments.length > 0"
    />
    <SummaryLink
      v-if="!readonly"
      :trip-id="trip.id"
    />
    <MyBankAccount
      v-if="editable"
      :account="myAccount"
      @edit="$emit('editAccount')"
    />
    <CloseTripSection
      v-if="editable"
      :trip-id="trip.id"
      :closed="trip.closed"
      :refresh="refresh"
    />
    <TransferSheet
      :trip="trip"
      :transfer="split ? null : paying"
      :accounts="accounts"
      :on-recorded="recorded"
      @close="paying = null"
      @add-account="addAccount"
    />
    <ConfirmSheet
      :open="removal.target.value !== null"
      danger
      :title="t('balances.deleteTitle')"
      :message="t('balances.deleteBody')"
      :confirm-label="t('balances.deleteConfirm')"
      :pending="removal.pending.value"
      :error="removal.error.value ? t(errorMessageKey(removal.error.value)) : undefined"
      @confirm="removal.confirm"
      @cancel="removal.cancel"
    />
  </div>
</template>
