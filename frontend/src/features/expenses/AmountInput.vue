<script setup lang="ts">
import { computed, ref, useId, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  caretAfter,
  formatAmountText,
  normaliseAmountText,
  parseAmountText,
  significantBefore,
} from '@/features/expenses/amountText'
import type { AppLocale } from '@/lib/i18n'

/** Numeric value in units of 10^-exponent (minor currency units or basis points), or null if empty. */
const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    /** Decimal precision: 0 for VND, 2 for USD cents or percent in basis points. */
    exponent: number
    suffix: string
    label: string
    error?: string
    compact?: boolean
  }>(),
  { error: undefined, compact: false },
)

const { locale } = useI18n()
const id = useId()
const field = useTemplateRef('field')
const appLocale = computed(() => locale.value as AppLocale)
const text = ref(model.value === null ? '' : formatAmountText(model.value, props.exponent, appLocale.value))

// Sync externally updated model values without clobbering active typing format.
watch(model, (value) => {
  if (value === parseAmountText(text.value, props.exponent, appLocale.value)) return
  text.value = value === null ? '' : formatAmountText(value, props.exponent, appLocale.value)
})

function onInput(): void {
  const input = field.value
  if (!input) return
  const kept = significantBefore(input.value, input.selectionStart ?? input.value.length, appLocale.value)
  const cleaned = normaliseAmountText(input.value, props.exponent, appLocale.value)
  text.value = cleaned
  input.value = cleaned
  const caret = caretAfter(cleaned, kept, appLocale.value)
  input.setSelectionRange(caret, caret)
  model.value = parseAmountText(cleaned, props.exponent, appLocale.value)
}
</script>

<template>
  <div
    class="flex min-w-0 flex-col items-center gap-1"
    :class="compact && 'w-full'"
  >
    <label
      :for="id"
      class="sr-only"
    >{{ label }}</label>
    <div
      class="flex w-full items-baseline justify-center gap-1"
      :class="compact && 'ink-border rounded-card bg-surface px-2'"
    >
      <input
        :id="id"
        ref="field"
        :value="text"
        type="text"
        :inputmode="exponent > 0 ? 'decimal' : 'numeric'"
        autocomplete="off"
        placeholder="0"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="error ? `${id}-error` : undefined"
        class="min-w-0 flex-1 rounded-card bg-transparent tabular-nums focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        :class="compact ? 'min-h-11 text-right' : 'font-heading min-h-16 text-center text-5xl font-semibold'"
        @input="onInput"
      >
      <span
        class="text-muted shrink-0"
        :class="compact ? 'text-sm' : 'font-heading text-3xl'"
        aria-hidden="true"
      >{{ suffix }}</span>
    </div>
    <p
      v-if="error"
      :id="`${id}-error`"
      role="alert"
      class="text-danger text-sm"
    >
      {{ error }}
    </p>
  </div>
</template>
