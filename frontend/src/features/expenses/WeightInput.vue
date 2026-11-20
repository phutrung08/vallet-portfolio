<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Minus, Plus } from 'lucide-vue-next'
import type { SplitMode } from '@/entities'
import AmountInput from '@/features/expenses/AmountInput.vue'
import { MAX_SHARES } from '@/features/expenses/splitDraft'

/** Input control for one participant's weight (`shares`, `percent`, or `exact`). */
const props = defineProps<{
  mode: Exclude<SplitMode, 'equal'>
  name: string
  value: number | null
  exponent: number
  symbol: string
}>()
const emit = defineEmits<{ change: [value: number | null] }>()

const { t } = useI18n()
const stepButton =
  'flex size-11 shrink-0 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-sky disabled:opacity-40'

function step(delta: number): void {
  emit('change', Math.min(MAX_SHARES, Math.max(0, (props.value ?? 0) + delta)))
}
</script>

<template>
  <div
    v-if="mode === 'shares'"
    class="ink-border rounded-pill bg-surface flex items-center"
  >
    <button
      type="button"
      :class="stepButton"
      :aria-label="t('expenseForm.fewerShares', { name })"
      :disabled="(value ?? 0) <= 0"
      @click="step(-1)"
    >
      <Minus
        :size="16"
        aria-hidden="true"
      />
    </button>
    <span
      class="min-w-6 text-center font-medium tabular-nums"
      aria-live="polite"
    >{{ value }}</span>
    <button
      type="button"
      :class="stepButton"
      :aria-label="t('expenseForm.moreShares', { name })"
      :disabled="(value ?? 0) >= MAX_SHARES"
      @click="step(1)"
    >
      <Plus
        :size="16"
        aria-hidden="true"
      />
    </button>
  </div>
  <AmountInput
    v-else
    :model-value="value"
    compact
    :exponent="mode === 'percent' ? 2 : exponent"
    :suffix="mode === 'percent' ? '%' : symbol"
    :label="t(mode === 'percent' ? 'expenseForm.percentOf' : 'expenseForm.amountOf', { name })"
    @update:model-value="emit('change', $event)"
  />
</template>
