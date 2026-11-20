<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import TextField from '@/components/TextField.vue'
import type { Bank, BankAccount } from '@/entities'
import BankPicker from '@/features/bank/BankPicker.vue'
import { digitsOnly, finalAccountName, typedAccountName } from '@/features/bank/accountRules'
import { useBankAccountForm } from '@/features/bank/useBankAccountForm'
import { api } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useAsyncData } from '@/lib/useAsyncData'

const props = defineProps<{
  tripId: string
  current: BankAccount | null
  onSaved: () => Promise<void>
}>()
defineEmits<{ remove: [] }>()

const { t } = useI18n()
const banks = useAsyncData(async (signal) => (await api.get<{ banks: Bank[] }>('/banks', { signal })).banks)
const { form, errors, submitError, pending, submit } = useBankAccountForm(
  () => props.tripId,
  props.current,
  props.onSaved,
)
const printed = computed(() => finalAccountName(form.name))
const message = (key: string | undefined) => (key ? t(`bank.errors.${key}`) : undefined)
</script>

<template>
  <div
    v-if="banks.status.value === 'loading'"
    aria-busy="true"
  >
    <span class="sr-only">{{ t('common.loading') }}</span>
    <div class="card-ink bg-sand h-36 animate-pulse motion-reduce:animate-none" />
  </div>
  <ErrorNotice
    v-else-if="banks.status.value === 'error' || !banks.data.value"
    :message="t(errorMessageKey(banks.error.value))"
    @retry="banks.reload"
  />
  <form
    v-else
    class="flex flex-col gap-4"
    novalidate
    @submit.prevent="submit"
  >
    <p
      v-if="current"
      class="text-muted text-sm"
    >
      {{ t('bank.current', { bank: current.bank_short_name, last4: current.account_last4 }) }}
    </p>
    <BankPicker
      v-model="form.bin"
      :banks="banks.data.value"
      :error="message(errors.bank)"
    />
    <TextField
      v-model="form.number"
      :label="t('bank.number')"
      inputmode="numeric"
      :normalise="digitsOnly"
      :error="message(errors.number)"
    />
    <div class="flex flex-col gap-1">
      <TextField
        v-model="form.name"
        :label="t('bank.name')"
        :normalise="typedAccountName"
        :error="message(errors.name)"
      />
      <p
        v-if="printed"
        class="text-muted text-sm"
      >
        {{ t('bank.printed', { name: printed }) }}
      </p>
    </div>
    <p
      v-if="submitError"
      role="alert"
      class="text-danger text-sm"
    >
      {{ t(errorMessageKey(submitError)) }}
    </p>
    <BaseButton
      type="submit"
      variant="success"
      block
      :disabled="pending"
    >
      {{ pending ? t('bank.saving') : t('bank.save') }}
    </BaseButton>
    <BaseButton
      v-if="current"
      variant="danger-outline"
      block
      @click="$emit('remove')"
    >
      {{ t('bank.remove') }}
    </BaseButton>
  </form>
</template>
