<script setup lang="ts">
import { computed, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ChevronLeft, Share2 } from 'lucide-vue-next'
import BottomNav from '@/components/BottomNav.vue'
import CachedNotice from '@/components/CachedNotice.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import PullIndicator from '@/components/PullIndicator.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SplitLayout from '@/components/SplitLayout.vue'
import type { Expense } from '@/entities'
import DeleteExpenseSheet from '@/features/expenses/DeleteExpenseSheet.vue'
import TripHistory from '@/features/expenses/TripHistory.vue'
import { useAddExpense } from '@/features/expenses/useAddExpense'
import { useDeleteExpense } from '@/features/expenses/useDeleteExpense'
import { useExpenseSelection } from '@/features/expenses/useExpenseSelection'
import TripDetailPane from '@/features/trips/TripDetailPane.vue'
import TripSummaryCard from '@/features/trips/TripSummaryCard.vue'
import { useTripPage } from '@/features/trips/useTripPage'
import { ApiError } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useTripSource } from '@/lib/tripSource'
import { useNavLabels } from '@/lib/useNavLabels'
import { usePullToRefresh } from '@/lib/usePullToRefresh'
import { useSplit } from '@/lib/useSplit'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const source = useTripSource()
const tripId = computed(() => String(route.params.tripId))
const { trip, days, fund, spentTotal, status, error, cachedCopy, reload, refresh } = useTripPage(
  () => tripId.value,
  source.read,
)
watch(tripId, reload)
const history = useTemplateRef('history')
const split = useSplit()
const selection = useExpenseSelection(split)

// Reload summary card and day history in place on deletion so the current day stays active.
const deletion = useDeleteExpense(
  () => tripId.value,
  async (expense) => {
    await Promise.all([refresh(), history.value?.invalidate(expense.spent_on)])
    if (days.value.length === 0) await router.replace({ query: {} })
  },
)

// Refresh trip totals and day tabs before updating query params so newly created days load immediately.
async function onSaved(saved: Expense): Promise<void> {
  await Promise.all([refresh(), history.value?.refreshDays()])
  await router.replace({ query: { day: saved.spent_on, expense: saved.id } })
}

const layout = useTemplateRef('layout')
const pull = usePullToRefresh(computed(() => layout.value?.listPane ?? null), () =>
  Promise.all([refresh(), history.value?.refreshDays()]),
)

const navLabels = useNavLabels()
const iconLink =
  'flex min-h-11 items-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky'

const addExpense = useAddExpense(() => tripId.value)
</script>

<template>
  <SplitLayout ref="layout">
    <template #list>
      <PullIndicator
        :offset="pull.offset.value"
        :armed="pull.armed.value"
        :refreshing="pull.refreshing.value"
      />
      <header class="flex items-center gap-1">
        <RouterLink
          to="/"
          :class="[iconLink, '-ml-2 justify-center px-2']"
          :aria-label="t('trip.back')"
        >
          <ChevronLeft
            :size="22"
            aria-hidden="true"
          />
        </RouterLink>
        <h1
          v-if="trip"
          class="min-w-0 flex-1 text-2xl break-words"
        >
          {{ trip.name }}
        </h1>
        <RefreshButton
          v-if="trip"
          :refreshing="pull.refreshing.value"
          @refresh="pull.refresh"
        />
        <RouterLink
          v-if="trip && !source.readonly"
          :to="`/trips/${encodeURIComponent(trip.id)}/members`"
          :class="[iconLink, '-mr-2 size-11 justify-center']"
          :aria-label="t('trip.share')"
        >
          <Share2
            :size="22"
            aria-hidden="true"
          />
        </RouterLink>
      </header>

      <div
        v-if="status === 'loading'"
        aria-busy="true"
      >
        <span class="sr-only">{{ t('common.loading') }}</span>
        <div class="card-ink bg-sand h-36 animate-pulse motion-reduce:animate-none" />
      </div>
      <ErrorNotice
        v-else-if="status === 'error'"
        :message="t(errorMessageKey(error))"
        :can-retry="!(error instanceof ApiError && error.code === 'not_found')"
        @retry="reload"
      />
      <template v-else-if="trip">
        <CachedNotice :copy="cachedCopy" />
        <TripSummaryCard
          :trip="trip"
          :fund="fund"
          :spent-total="spentTotal"
        />
        <TripHistory
          ref="history"
          :trip="trip"
          :days="days"
          :split="split"
          :selected-id="selection.selectedId.value"
          @delete="deletion.ask"
          @select="selection.select"
          @shown="selection.listShown"
        />
      </template>
    </template>
    <template #detail>
      <TripDetailPane
        v-if="split && trip"
        :trip="trip"
        :selected-id="selection.selectedId.value"
        :has-expenses="days.length > 0"
        @delete="deletion.ask"
        @saved="onSaved"
      />
    </template>
  </SplitLayout>
  <DeleteExpenseSheet
    :open="deletion.target.value !== null"
    :pending="deletion.pending.value"
    :error="deletion.error.value"
    @confirm="deletion.confirm"
    @cancel="deletion.cancel"
  />
  <BottomNav
    v-if="trip"
    :trip-id="trip.id"
    :labels="navLabels"
    @add="addExpense"
  />
</template>
