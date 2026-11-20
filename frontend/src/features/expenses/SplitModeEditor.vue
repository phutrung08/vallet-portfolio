<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SplitMode, TripMember } from '@/entities'
import ParticipantGrid from '@/features/expenses/ParticipantGrid.vue'
import {
  FULL_BASIS_POINTS,
  participants,
  splitProblem,
  weightTotal,
  type SplitDraft,
} from '@/features/expenses/splitDraft'
import { useFieldMessage } from '@/features/expenses/useFieldMessage'
import { formatBasisPoints, formatMoney, type CurrencyCode } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

const props = defineProps<{
  candidates: readonly TripMember[]
  draft: SplitDraft
  preview: ReadonlyMap<string, number> | null
  amount: number | null
  currency: CurrencyCode
  /** Error message returned by validation or the API on submit. */
  error?: string
}>()
const emit = defineEmits<{
  mode: [mode: SplitMode]
  toggle: [id: string]
  weight: [id: string, value: number | null]
}>()

const MODES: readonly SplitMode[] = ['equal', 'shares', 'percent', 'exact']
const { t, locale } = useI18n()
const name = useId()
const message = useFieldMessage(() => props.currency)
const count = computed(() => participants(props.draft, props.candidates).length)

/** Live total vs target progress line for percent and exact split modes. */
const status = computed(() => {
  const total = weightTotal(props.draft, props.candidates)
  const appLocale = locale.value as AppLocale
  let line: string
  if (props.draft.mode === 'percent') {
    line = t('expenseForm.total', {
      total: formatBasisPoints(total, appLocale),
      target: formatBasisPoints(FULL_BASIS_POINTS, appLocale),
    })
  } else if (props.draft.mode === 'exact' && props.amount !== null) {
    line = t('expenseForm.total', {
      total: formatMoney(total, props.currency, appLocale),
      target: formatMoney(props.amount, props.currency, appLocale),
    })
  } else return null
  const problem = splitProblem(props.draft, props.candidates, props.amount)
  const gap = problem?.key === 'missing' || problem?.key === 'excess' ? message(problem) : undefined
  return { line, gap }
})

// Upgrades the live gap line into the error alert in place so it is never duplicated.
const gapIsError = computed(() => props.error !== undefined && props.error === status.value?.gap)
</script>

<template>
  <section class="flex flex-col gap-3">
    <h2 class="text-lg">
      {{ t('expenseForm.splitAmong', count) }}
    </h2>
    <fieldset>
      <legend class="sr-only">
        {{ t('expenseForm.mode') }}
      </legend>
      <div class="grid grid-cols-4 gap-2">
        <label
          v-for="mode in MODES"
          :key="mode"
          class="min-w-0"
        >
          <input
            type="radio"
            :name="name"
            :value="mode"
            :checked="draft.mode === mode"
            class="peer sr-only"
            @change="emit('mode', mode)"
          >
          <span
            class="ink-border rounded-pill bg-surface flex min-h-11 cursor-pointer items-center justify-center px-1 text-center text-sm font-medium min-[360px]:px-2 peer-checked:bg-ink peer-checked:text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-sky"
          >{{ t(`expenseForm.modes.${mode}`) }}</span>
        </label>
      </div>
    </fieldset>
    <ParticipantGrid
      :candidates="candidates"
      :draft="draft"
      :preview="preview"
      :currency="currency"
      @toggle="emit('toggle', $event)"
      @weight="(id, value) => emit('weight', id, value)"
    />
    <p
      v-if="status"
      :role="gapIsError ? 'alert' : undefined"
      class="text-sm tabular-nums"
      :class="gapIsError ? 'text-danger' : 'text-muted'"
    >
      {{ status.line }}<template v-if="status.gap">
        · {{ status.gap }}
      </template>
    </p>
    <p
      v-if="error && !gapIsError"
      role="alert"
      class="text-danger text-sm"
    >
      {{ error }}
    </p>
    <p class="text-muted text-center text-xs">
      {{ t('expenseForm.hint') }}
    </p>
  </section>
</template>
