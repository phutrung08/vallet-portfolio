<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { X } from 'lucide-vue-next'
import ErrorNotice from '@/components/ErrorNotice.vue'
import type { Expense } from '@/entities'
import DeleteExpenseSheet from '@/features/expenses/DeleteExpenseSheet.vue'
import ExpenseForm from '@/features/expenses/ExpenseForm.vue'
import { useDeleteExpense } from '@/features/expenses/useDeleteExpense'
import { useExpensePage } from '@/features/expenses/useExpensePage'
import { localIsoDate } from '@/features/trips/tripMeta'
import { errorMessageKey } from '@/lib/errors'

// Injectable clock lets tests fix "today" deterministically.
const props = withDefaults(defineProps<{ now?: () => Date }>(), { now: () => new Date() })

const { t } = useI18n()
const router = useRouter()
const { tripId, trip, expense, editing, status, error, notFound, readOnlyKey, reload } = useExpensePage()
const deletion = useDeleteExpense(
  () => tripId,
  async (deleted) => {
    await router.replace({ path: `/trips/${tripId}`, query: { day: deleted.spent_on } })
  },
)

async function openSavedDay(saved: Expense): Promise<void> {
  await router.replace({ path: `/trips/${tripId}`, query: { day: saved.spent_on } })
}
</script>

<template>
  <main class="col-center flex min-h-dvh flex-col gap-4 p-4">
    <header class="flex items-center gap-1">
      <RouterLink
        :to="`/trips/${tripId}`"
        :aria-label="t('expenseForm.close')"
        class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      >
        <X
          :size="22"
          aria-hidden="true"
        />
      </RouterLink>
      <h1 class="text-2xl">
        {{ editing ? t('expense.edit') : t('nav.add') }}
      </h1>
    </header>

    <div
      v-if="status === 'loading'"
      aria-busy="true"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
      <div class="card-ink bg-sand h-48 animate-pulse motion-reduce:animate-none" />
    </div>
    <ErrorNotice
      v-else-if="status === 'error'"
      :message="notFound && editing ? t('expense.notFound') : t(errorMessageKey(error))"
      :can-retry="!notFound"
      @retry="reload"
    />
    <ErrorNotice
      v-else-if="readOnlyKey"
      :message="t(readOnlyKey)"
      :can-retry="false"
    />
    <template v-else-if="trip">
      <ExpenseForm
        :trip="trip"
        :expense="expense"
        :today="localIsoDate(props.now())"
        @reload="reload"
        @saved="openSavedDay"
        @delete="expense && deletion.ask(expense)"
      />
      <DeleteExpenseSheet
        :open="deletion.target.value !== null"
        :pending="deletion.pending.value"
        :error="deletion.error.value"
        @confirm="deletion.confirm"
        @cancel="deletion.cancel"
      />
    </template>
  </main>
</template>
