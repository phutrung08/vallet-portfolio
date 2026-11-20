<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BottomSheet from '@/components/BottomSheet.vue'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import type { BankAccount } from '@/entities'
import BankAccountForm from '@/features/bank/BankAccountForm.vue'
import { api } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

const props = defineProps<{
  open: boolean
  tripId: string
  current: BankAccount | null
  /** Callback run after save or removal; closes the sheet once completed. */
  changed: () => Promise<void>
}>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const removal = useConfirmedAction<'remove'>(async () => {
  await api.delete<void>(`/trips/${encodeURIComponent(props.tripId)}/members/me/bank-account`)
  await props.changed()
  emit('close')
})

async function saved(): Promise<void> {
  await props.changed()
  emit('close')
}
</script>

<template>
  <BottomSheet
    :open="open"
    :title="t('bank.title')"
    @close="emit('close')"
  >
    <BankAccountForm
      :trip-id="tripId"
      :current="current"
      :on-saved="saved"
      @remove="removal.ask('remove')"
    />
  </BottomSheet>
  <ConfirmSheet
    :open="removal.target.value !== null"
    danger
    :title="t('bank.removeTitle')"
    :message="t('bank.removeBody')"
    :confirm-label="t('bank.removeConfirm')"
    :pending="removal.pending.value"
    :error="removal.error.value ? t(errorMessageKey(removal.error.value)) : undefined"
    @confirm="removal.confirm"
    @cancel="removal.cancel"
  />
</template>
