<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import type { BankAccount, Transfer, TripDetail } from '@/entities'
import AccountChangedNotice from '@/features/balances/AccountChangedNotice.vue'
import QrDetails from '@/features/balances/QrDetails.vue'
import { changedRecently } from '@/features/balances/balanceRules'
import { useTransferPay } from '@/features/balances/useTransferPay'
import AmountInput from '@/features/expenses/AmountInput.vue'
import { errorMessageKey } from '@/lib/errors'
import { EXPONENTS, SYMBOLS } from '@/lib/format'
import { useCopy } from '@/lib/useCopy'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{
  trip: TripDetail
  transfer: Transfer
  accounts: readonly BankAccount[]
  onRecorded: () => Promise<void>
}>()
defineEmits<{ addAccount: [] }>()

const { t } = useI18n()
const money = useMoney(() => props.trip.currency)
const pay = useTransferPay(() => props.trip.id, props.transfer, props.onRecorded)
const { copyState, copy } = useCopy(() =>
  pay.amount.value === null ? null : String(pay.amount.value),
)
const payeeName = computed(
  () => props.trip.members.find((member) => member.id === props.transfer.payee)?.display_name ?? '',
)
const accountChangedAt = computed(() => {
  const account = props.accounts.find((item) => item.member_id === props.transfer.payee)
  const changedAt = account?.bank_account_changed_at ?? null
  return changedRecently(changedAt, new Date()) ? changedAt : null
})
const amountMessage = computed(() => {
  const key = pay.amountError.value
  if (key === null) return undefined
  return t(`balances.qr.errors.${key}`, { max: money(props.transfer.amount) })
})
</script>

<template>
  <div class="flex flex-col gap-4">
    <AmountInput
      v-model="pay.amount.value"
      compact
      :exponent="EXPONENTS[trip.currency]"
      :suffix="SYMBOLS[trip.currency]"
      :label="t('balances.qr.amount')"
      :error="amountMessage"
    />

    <div
      v-if="pay.qrStatus.value === 'loading'"
      aria-busy="true"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
      <div class="card-ink bg-sand mx-auto size-60 max-w-full animate-pulse motion-reduce:animate-none" />
    </div>
    <template v-else-if="pay.qr.value">
      <AccountChangedNotice
        v-if="accountChangedAt"
        :name="payeeName"
        :changed-at="accountChangedAt"
      />
      <QrDetails :qr="pay.qr.value" />
    </template>
    <div
      v-else-if="pay.qrErrorCode.value === 'no_bank_account'"
      class="card-ink bg-sand flex flex-col items-start gap-2 p-3"
    >
      <p role="alert">
        {{ t('balances.qr.noAccount', { name: payeeName }) }}
      </p>
      <BaseButton
        v-if="transfer.payee === trip.me"
        variant="outline"
        @click="$emit('addAccount')"
      >
        {{ t('balances.qr.addAccount') }}
      </BaseButton>
    </div>
    <p
      v-else-if="pay.qrErrorCode.value === 'currency_not_supported'"
      role="alert"
      class="card-ink bg-sand p-3"
    >
      {{ t('balances.qr.unsupported') }}
    </p>
    <ErrorNotice
      v-else-if="pay.qrStatus.value === 'error'"
      :message="t(errorMessageKey(pay.qrError.value))"
      @retry="pay.loadQr"
    />

    <BaseButton
      v-if="pay.amountError.value === null"
      variant="outline"
      block
      @click="copy"
    >
      <Copy
        :size="16"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ copyState === 'copied' ? t('balances.qr.copied') : t('balances.qr.copy') }}
    </BaseButton>
    <p
      v-if="copyState === 'failed'"
      role="alert"
      class="text-danger text-sm"
    >
      {{ t('balances.qr.copyFailed') }}
    </p>
    <p
      v-if="pay.recordError.value"
      role="alert"
      class="text-danger text-sm"
    >
      {{ t(errorMessageKey(pay.recordError.value)) }}
    </p>
    <BaseButton
      variant="success"
      block
      :disabled="pay.pending.value || pay.amountError.value !== null"
      @click="pay.record"
    >
      {{ pay.pending.value ? t('balances.qr.recording') : t('balances.qr.done') }}
    </BaseButton>
  </div>
</template>
