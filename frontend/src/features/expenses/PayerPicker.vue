<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, ChevronRight, PiggyBank } from 'lucide-vue-next'
import BaseAvatar from '@/components/BaseAvatar.vue'
import BottomSheet from '@/components/BottomSheet.vue'
import type { TripDetail, TripMember } from '@/entities'

/** Member ID or null when paid by the shared fund. */
const model = defineModel<string | null>({ required: true })
/** Candidate payers ordered by position (see `splitCandidates`). */
const props = defineProps<{ trip: TripDetail; members: readonly TripMember[]; error?: string }>()

const { t } = useI18n()
const open = ref(false)

interface Option {
  id: string | null
  name: string
}

const options = computed<Option[]>(() => {
  const members = props.members.map((member) => {
    let name = member.display_name
    if (member.id === props.trip.me) name = t('expenseForm.you', { name })
    else if (member.removed) name = t('expenseForm.left', { name })
    return { id: member.id, name }
  })
  const fund = props.trip.fund_holder_id === null ? [] : [{ id: null, name: t('expense.fundName') }]
  return [...members, ...fund]
})
const selected = computed(() => options.value.find((option) => option.id === model.value))

function choose(id: string | null): void {
  model.value = id
  open.value = false
}
</script>

<template>
  <div class="flex flex-col gap-1">
    <button
      type="button"
      aria-haspopup="dialog"
      class="ink-border rounded-card bg-surface flex min-h-14 w-full items-center gap-3 px-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      @click="open = true"
    >
      <span class="text-muted text-sm">{{ t('expenseForm.payer') }}</span>
      <span class="flex min-w-0 flex-1 items-center justify-end gap-2 font-medium">
        <PiggyBank
          v-if="selected?.id === null"
          :size="22"
          aria-hidden="true"
        />
        <BaseAvatar
          v-else-if="selected"
          :name="selected.name"
        />
        <span class="truncate">{{ selected?.name }}</span>
      </span>
      <ChevronRight
        :size="18"
        class="text-muted shrink-0"
        aria-hidden="true"
      />
    </button>
    <p
      v-if="error"
      role="alert"
      class="text-danger text-sm"
    >
      {{ error }}
    </p>
    <BottomSheet
      :open="open"
      :title="t('expenseForm.payerSheet')"
      @close="open = false"
    >
      <ul class="flex flex-col gap-1">
        <li
          v-for="option in options"
          :key="option.id ?? 'fund'"
        >
          <button
            type="button"
            :aria-pressed="option.id === model"
            class="rounded-card flex min-h-12 w-full items-center gap-3 px-2 text-left focus-visible:outline-2 focus-visible:outline-sky aria-pressed:bg-sand"
            @click="choose(option.id)"
          >
            <PiggyBank
              v-if="option.id === null"
              :size="22"
              aria-hidden="true"
            />
            <BaseAvatar
              v-else
              :name="option.name"
            />
            <span class="min-w-0 flex-1 break-words">{{ option.name }}</span>
            <Check
              v-if="option.id === model"
              :size="18"
              aria-hidden="true"
            />
          </button>
        </li>
      </ul>
    </BottomSheet>
  </div>
</template>
