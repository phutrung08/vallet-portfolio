<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { X } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import type { Expense, TripDetail } from '@/entities'
import ExpenseDetailBody from '@/features/expenses/ExpenseDetailBody.vue'
import ExpenseForm from '@/features/expenses/ExpenseForm.vue'
import { readOnlyKeyOf } from '@/features/expenses/expenseFacts'
import { localIsoDate } from '@/features/trips/tripMeta'
import { ApiError } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useTripSource } from '@/lib/tripSource'
import { useAsyncData } from '@/lib/useAsyncData'

/**
 * Split-screen detail pane showing an expense with inline Edit mode and Delete trigger.
 */
const props = withDefaults(
  defineProps<{ trip: TripDetail; expenseId: string; today?: string }>(),
  { today: () => localIsoDate(new Date()) },
)
const emit = defineEmits<{ delete: [expense: Expense]; saved: [expense: Expense] }>()

const { t } = useI18n()
const { read, readonly } = useTripSource()
const { data: expense, status, error, reload } = useAsyncData((signal) =>
  read<Expense>(
    `/trips/${encodeURIComponent(props.trip.id)}/expenses/${encodeURIComponent(props.expenseId)}`,
    signal,
  ),
)
const route = useRoute()
const router = useRouter()
// Opens edit mode once when redirected from `/edit` on wide layouts, then clears `?edit=yes`.
const editing = ref(route.query.edit === 'yes')
if (editing.value) void router.replace({ query: { ...route.query, edit: undefined } })
const readOnlyKey = computed(() => readOnlyKeyOf(props.trip))

watch(
  () => props.expenseId,
  () => {
    editing.value = false
    void reload()
  },
)

async function onSaved(saved: Expense): Promise<void> {
  editing.value = false
  emit('saved', saved)
  await reload()
}
</script>

<template>
  <section class="flex flex-1 flex-col gap-4">
    <div
      v-if="status === 'loading'"
      aria-busy="true"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
      <div class="card-ink bg-sand h-48 animate-pulse motion-reduce:animate-none" />
    </div>
    <ErrorNotice
      v-else-if="status === 'error'"
      :message="error instanceof ApiError && error.code === 'not_found' ? t('expense.notFound') : t(errorMessageKey(error))"
      :can-retry="!(error instanceof ApiError && error.code === 'not_found')"
      @retry="reload"
    />
    <template v-else-if="expense && editing">
      <header class="flex items-center gap-1">
        <button
          type="button"
          :aria-label="t('expenseForm.close')"
          class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
          @click="editing = false"
        >
          <X
            :size="22"
            aria-hidden="true"
          />
        </button>
        <h2 class="text-2xl">
          {{ t('expense.edit') }}
        </h2>
      </header>
      <ExpenseForm
        :trip="trip"
        :expense="expense"
        :today="today"
        @reload="reload"
        @delete="emit('delete', expense)"
        @saved="onSaved"
      />
    </template>
    <template v-else-if="expense">
      <h2 class="text-2xl break-words">
        {{ expense.title }}
      </h2>
      <ExpenseDetailBody
        :trip="trip"
        :expense="expense"
      />
      <p
        v-if="readOnlyKey"
        class="text-sm"
      >
        {{ t(readOnlyKey) }}
      </p>
      <div
        v-else-if="!readonly"
        class="mt-auto flex flex-col gap-2"
      >
        <BaseButton
          block
          @click="editing = true"
        >
          {{ t('expense.edit') }}
        </BaseButton>
        <BaseButton
          variant="danger-outline"
          block
          @click="emit('delete', expense)"
        >
          {{ t('expense.delete') }}
        </BaseButton>
      </div>
    </template>
  </section>
</template>
