<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseAvatar from '@/components/BaseAvatar.vue'
import type { TripMember } from '@/entities'
import WeightInput from '@/features/expenses/WeightInput.vue'
import { weightOf, type SplitDraft } from '@/features/expenses/splitDraft'
import { EXPONENTS, SYMBOLS, formatMoney, type CurrencyCode } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

const props = defineProps<{
  candidates: readonly TripMember[]
  draft: SplitDraft
  preview: ReadonlyMap<string, number> | null
  currency: CurrencyCode
}>()
const emit = defineEmits<{ toggle: [id: string]; weight: [id: string, value: number | null] }>()

const { t, locale } = useI18n()
const mode = computed(() => (props.draft.mode === 'equal' ? null : props.draft.mode))

function shareLine(id: string): string {
  if (!props.draft.included.includes(id)) return t('expenseForm.out')
  const amount = props.preview?.get(id)
  return amount === undefined ? '–' : formatMoney(amount, props.currency, locale.value as AppLocale)
}
</script>

<template>
  <ul
    class="grid gap-x-2 gap-y-3"
    :class="mode ? 'grid-cols-2' : 'grid-cols-3'"
  >
    <li
      v-for="member in candidates"
      :key="member.id"
      class="flex min-w-0 flex-col items-stretch gap-1"
    >
      <button
        type="button"
        :aria-pressed="draft.included.includes(member.id)"
        class="rounded-card flex min-h-11 w-full flex-col items-center gap-1 px-1 py-1.5 focus-visible:outline-2 focus-visible:outline-sky"
        @click="emit('toggle', member.id)"
      >
        <BaseAvatar
          :name="member.display_name"
          size="lg"
          :muted="!draft.included.includes(member.id)"
        />
        <span class="w-full truncate text-center text-sm font-medium">{{ member.display_name }}</span>
        <span
          v-if="member.removed"
          class="text-muted text-xs"
        >{{ t('expenseForm.leftTag') }}</span>
        <span
          class="text-xs tabular-nums"
          :class="draft.included.includes(member.id) ? 'text-ink' : 'text-muted'"
        >{{ shareLine(member.id) }}</span>
      </button>
      <WeightInput
        v-if="mode && draft.included.includes(member.id)"
        :mode="mode"
        :name="member.display_name"
        :value="weightOf(draft, member.id)"
        :exponent="EXPONENTS[currency]"
        :symbol="SYMBOLS[currency]"
        @change="emit('weight', member.id, $event)"
      />
    </li>
  </ul>
</template>
