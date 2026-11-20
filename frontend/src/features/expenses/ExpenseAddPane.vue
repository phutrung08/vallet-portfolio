<script setup lang="ts">
import { onMounted, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'
import type { Expense, TripDetail } from '@/entities'
import ExpenseForm from '@/features/expenses/ExpenseForm.vue'
import { localIsoDate } from '@/features/trips/tripMeta'

/** Inline Add-mode view for the trip right pane on split viewports. */
withDefaults(defineProps<{ trip: TripDetail; closable: boolean; today?: string }>(), {
  today: () => localIsoDate(new Date()),
})
const emit = defineEmits<{ close: []; saved: [expense: Expense] }>()

const { t } = useI18n()
const root = useTemplateRef('root')
onMounted(() => root.value?.querySelector('input')?.focus())
</script>

<template>
  <section
    ref="root"
    class="flex flex-1 flex-col gap-4"
  >
    <header class="flex items-center gap-1">
      <button
        v-if="closable"
        type="button"
        :aria-label="t('expenseForm.close')"
        class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        @click="emit('close')"
      >
        <X
          :size="22"
          aria-hidden="true"
        />
      </button>
      <h2 class="text-2xl">
        {{ t('nav.add') }}
      </h2>
    </header>
    <ExpenseForm
      :trip="trip"
      :today="today"
      @saved="emit('saved', $event)"
    />
  </section>
</template>
