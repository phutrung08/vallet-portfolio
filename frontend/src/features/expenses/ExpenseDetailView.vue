<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import DeleteExpenseSheet from '@/features/expenses/DeleteExpenseSheet.vue'
import ExpenseDetailBody from '@/features/expenses/ExpenseDetailBody.vue'
import { useDeleteExpense } from '@/features/expenses/useDeleteExpense'
import { useExpensePage } from '@/features/expenses/useExpensePage'
import { errorMessageKey } from '@/lib/errors'

const { t } = useI18n()
const router = useRouter()
const { tripId, trip, expense, status, error, notFound, readOnlyKey, reload } = useExpensePage()
const deletion = useDeleteExpense(
  () => tripId,
  async (deleted) => {
    await router.replace({ path: `/trips/${tripId}`, query: { day: deleted.spent_on } })
  },
)
</script>

<template>
  <main class="col-center flex min-h-dvh flex-col gap-4 p-4">
    <header class="flex items-center gap-1">
      <RouterLink
        :to="`/trips/${tripId}`"
        :aria-label="t('trip.back')"
        class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      >
        <ChevronLeft
          :size="22"
          aria-hidden="true"
        />
      </RouterLink>
      <h1 class="min-w-0 flex-1 text-2xl break-words">
        {{ expense?.title }}
      </h1>
    </header>
    <p
      v-if="status === 'loading'"
      aria-busy="true"
      class="card-ink bg-sand h-48 animate-pulse motion-reduce:animate-none"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
    </p>
    <ErrorNotice
      v-else-if="status === 'error'"
      :message="notFound ? t('expense.notFound') : t(errorMessageKey(error))"
      :can-retry="!notFound"
      @retry="reload"
    />
    <template v-else-if="trip && expense">
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
        v-else
        class="mt-auto flex flex-col gap-2"
      >
        <RouterLink
          :to="`/trips/${tripId}/expenses/${expense.id}/edit`"
          class="ink-border rounded-pill shadow-hard bg-yellow text-on-yellow flex min-h-11 items-center justify-center font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        >
          {{ t('expense.edit') }}
        </RouterLink>
        <BaseButton
          variant="danger-outline"
          block
          @click="deletion.ask(expense)"
        >
          {{ t('expense.delete') }}
        </BaseButton>
      </div>
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
