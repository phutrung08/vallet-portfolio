<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { MapPin, Pencil, Split, StickyNote, Trash2, UserX } from 'lucide-vue-next'
import type { Expense, TripDetail } from '@/entities'
import { excludedNames, mapsUrl, perPerson } from '@/features/expenses/expenseFacts'
import { formatMoney } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'
import { useTripSource } from '@/lib/tripSource'

const props = defineProps<{ id: string; trip: TripDetail; expense: Expense }>()
defineEmits<{ delete: [] }>()

const MAX_NAMED_EXCLUDED = 2

const { t, locale } = useI18n()
const { readonly } = useTripSource()
const money = (minor: number) => formatMoney(minor, props.trip.currency, locale.value as AppLocale)

const perPersonLine = computed(() => {
  const share = perPerson(props.expense)
  if (share === null) return null
  if (share.kind === 'uneven') {
    return t('expense.unevenSplit', { min: money(share.min), max: money(share.max) })
  }
  return t('expense.perPerson', {
    amount: money(share.amount),
    mode: t(`expense.split.${share.mode}`),
  })
})
const excludedLine = computed(() => {
  const names = excludedNames(props.expense, props.trip.members)
  if (names.length === 0) return null
  const shown = names.slice(0, MAX_NAMED_EXCLUDED).join(', ')
  const hidden = names.length - MAX_NAMED_EXCLUDED
  return t('expense.excluded', {
    names: hidden > 0 ? t('expense.andMore', { names: shown, n: hidden }) : shown,
  })
})

const base = computed(() => `/trips/${props.trip.id}/expenses/${props.expense.id}`)
const iconButton =
  'flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-sky'
const factIcon = 'mt-0.5 shrink-0 text-muted'
</script>

<template>
  <div
    :id="id"
    class="border-line flex flex-col gap-2 border-t-[1.5px] px-3 pt-3 pb-1"
  >
    <ul class="flex flex-col gap-2 text-sm">
      <li
        v-if="perPersonLine"
        class="flex gap-2"
      >
        <Split
          :size="16"
          :class="factIcon"
          aria-hidden="true"
        />
        {{ perPersonLine }}
      </li>
      <li
        v-if="excludedLine"
        class="flex gap-2"
      >
        <UserX
          :size="16"
          :class="factIcon"
          aria-hidden="true"
        />
        {{ excludedLine }}
      </li>
      <li
        v-if="expense.note"
        class="flex gap-2"
      >
        <StickyNote
          :size="16"
          :class="factIcon"
          aria-hidden="true"
        />
        <p class="min-w-0 whitespace-pre-wrap break-words">
          {{ expense.note }}
        </p>
      </li>
      <li
        v-if="expense.place"
        class="flex gap-2"
      >
        <MapPin
          :size="16"
          :class="factIcon"
          aria-hidden="true"
        />
        <a
          :href="mapsUrl(expense.place)"
          target="_blank"
          rel="noopener noreferrer"
          class="flex min-h-11 min-w-0 items-center break-words underline"
        >{{ expense.place }}</a>
      </li>
    </ul>
    <div
      v-if="!readonly"
      class="flex items-center justify-between"
    >
      <RouterLink
        :to="base"
        class="flex min-h-11 items-center text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-sky"
      >
        {{ t('expense.details') }} ›
      </RouterLink>
      <div class="flex">
        <RouterLink
          :to="`${base}/edit`"
          :aria-label="t('expense.edit')"
          :class="iconButton"
        >
          <Pencil
            :size="18"
            aria-hidden="true"
          />
        </RouterLink>
        <button
          type="button"
          :aria-label="t('expense.delete')"
          :class="iconButton"
          @click="$emit('delete')"
        >
          <Trash2
            :size="18"
            aria-hidden="true"
          />
        </button>
      </div>
    </div>
  </div>
</template>
