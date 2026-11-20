<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import BottomSheet from '@/components/BottomSheet.vue'
import MemberPicker from '@/components/MemberPicker.vue'
import TextField from '@/components/TextField.vue'
import type { TripDetail } from '@/entities'
import AmountInput from '@/features/expenses/AmountInput.vue'
import type { ContributionError } from '@/features/fund/useContributionForm'
import { activeMembers } from '@/features/trips/tripMeta'
import { errorMessageKey } from '@/lib/errors'
import { EXPONENTS, SYMBOLS } from '@/lib/format'

const memberId = defineModel<string>('memberId', { required: true })
const amount = defineModel<number | null>('amount', { required: true })
const date = defineModel<string>('date', { required: true })
const props = defineProps<{
  open: boolean
  trip: TripDetail
  errors: Partial<Record<'amount' | 'date', ContributionError>>
  submitError: unknown
  pending: boolean
}>()
const emit = defineEmits<{ close: []; submit: [] }>()

const { t } = useI18n()
const options = computed(() =>
  activeMembers(props.trip).map((member) => ({ id: member.id, name: member.display_name })),
)
const message = (key: ContributionError | undefined) => (key ? t(`fund.errors.${key}`) : undefined)
</script>

<template>
  <BottomSheet
    :open="open"
    :title="t('fund.add')"
    @close="emit('close')"
  >
    <form
      class="flex flex-col gap-4"
      novalidate
      @submit.prevent="emit('submit')"
    >
      <MemberPicker
        v-model="memberId"
        :label="t('fund.who')"
        :options="options"
      />
      <AmountInput
        v-model="amount"
        :exponent="EXPONENTS[trip.currency]"
        :suffix="SYMBOLS[trip.currency]"
        :label="t('fund.amount')"
        :error="message(errors.amount)"
      />
      <TextField
        v-model="date"
        type="date"
        :label="t('fund.date')"
        :error="message(errors.date)"
      />
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
        {{ pending ? t('fund.saving') : t('fund.save') }}
      </BaseButton>
    </form>
  </BottomSheet>
</template>
