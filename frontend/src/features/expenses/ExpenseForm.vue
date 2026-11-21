<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import TextField from '@/components/TextField.vue'
import type { Expense, TripDetail } from '@/entities'
import AmountInput from '@/features/expenses/AmountInput.vue'
import CategoryPicker from '@/features/expenses/CategoryPicker.vue'
import NotePlaceFields from '@/features/expenses/NotePlaceFields.vue'
import PayerPicker from '@/features/expenses/PayerPicker.vue'
import SplitModeEditor from '@/features/expenses/SplitModeEditor.vue'
import { useExpenseForm } from '@/features/expenses/useExpenseForm'
import { useFieldMessage } from '@/features/expenses/useFieldMessage'
import { errorMessageKey } from '@/lib/errors'
import { EXPONENTS, SYMBOLS } from '@/lib/format'

const props = defineProps<{ trip: TripDetail; today: string; expense?: Expense }>()
const emit = defineEmits<{ reload: []; delete: []; saved: [expense: Expense] }>()

const { t } = useI18n()
const message = useFieldMessage(() => props.trip.currency)
const { form, draft, candidates, preview, errors, submitError, conflict, pending, toggle, setWeight, submit } =
  useExpenseForm(props.trip, props.today, (saved) => emit('saved', saved), props.expense)
const confirmingReload = ref(false)
</script>

<template>
  <form
    class="flex flex-1 flex-col gap-5"
    novalidate
    @submit.prevent="submit"
  >
    <AmountInput
      v-model="form.amount"
      :exponent="EXPONENTS[trip.currency]"
      :suffix="SYMBOLS[trip.currency]"
      :label="t('expenseForm.amount')"
      :error="message(errors.amount)"
    />
    <div class="flex flex-wrap items-start gap-3">
      <TextField
        v-model="form.title"
        class="min-w-40 flex-1"
        :label="t('expenseForm.title')"
        :placeholder="t('expenseForm.titlePlaceholder')"
        :error="message(errors.title)"
      />
      <TextField
        v-model="form.spentOn"
        type="date"
        class="w-36 shrink-0"
        :label="t('expenseForm.date')"
        :error="message(errors.spentOn)"
      />
    </div>
    <CategoryPicker v-model="form.category" />
    <PayerPicker
      v-model="form.paidBy"
      :trip="trip"
      :members="candidates"
      :error="message(errors.paidBy)"
    />
    <SplitModeEditor
      :candidates="candidates"
      :draft="draft"
      :preview="preview"
      :amount="form.amount"
      :currency="trip.currency"
      :error="message(errors.split)"
      @mode="draft.mode = $event"
      @toggle="toggle"
      @weight="setWeight"
    />
    <NotePlaceFields
      v-model:note="form.note"
      v-model:place="form.place"
      :note-error="message(errors.note)"
      :place-error="message(errors.place)"
    />
    <BaseButton
      v-if="expense"
      variant="danger-outline"
      block
      @click="$emit('delete')"
    >
      {{ t('expense.delete') }}
    </BaseButton>

    <div class="bg-cream border-line sticky bottom-0 z-10 -mx-4 mt-auto flex flex-col gap-2 border-t px-4 pt-3 pb-[calc(1rem+env(safe-area-inset-bottom))]">
      <div
        v-if="conflict"
        role="alert"
        class="flex flex-col items-start gap-2 text-sm"
      >
        <p class="text-danger">
          {{ t('expenseForm.conflict') }}
        </p>
        <BaseButton
          variant="outline"
          @click="confirmingReload = true"
        >
          {{ t('expenseForm.loadLatest') }}
        </BaseButton>
      </div>
      <p
        v-else-if="submitError"
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
        {{ pending ? t('expenseForm.saving') : t('expenseForm.save') }}
      </BaseButton>
    </div>
    <ConfirmSheet
      :open="confirmingReload"
      :title="t('expenseForm.discardTitle')"
      :message="t('expenseForm.discardBody')"
      :confirm-label="t('expenseForm.loadLatest')"
      @confirm="$emit('reload')"
      @cancel="confirmingReload = false"
    />
  </form>
</template>
