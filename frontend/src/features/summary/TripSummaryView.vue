<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import BottomNav from '@/components/BottomNav.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import { useAddExpense } from '@/features/expenses/useAddExpense'
import SummaryContent from '@/features/summary/SummaryContent.vue'
import { useTripSummary } from '@/features/summary/useTripSummary'
import { ApiError } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useDesktopBarTrip } from '@/lib/desktopBarContext'
import { useNavLabels, useNavShortLabels } from '@/lib/useNavLabels'

const { t } = useI18n()
const route = useRoute()
const tripId = computed(() => String(route.params.tripId))
const { trip, summary, status, error, reload } = useTripSummary(() => tripId.value)
watch(tripId, reload)
useDesktopBarTrip(() => trip.value)
const navLabels = useNavLabels()
const navShortLabels = useNavShortLabels()

const addExpense = useAddExpense(() => tripId.value)
</script>

<template>
  <main class="col-nav flex min-h-dvh max-w-md flex-col gap-4 p-4 pb-nav">
    <header class="flex items-center gap-1">
      <RouterLink
        :to="`/trips/${encodeURIComponent(tripId)}/balances`"
        :aria-label="t('trip.back')"
        class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      >
        <ChevronLeft
          :size="22"
          aria-hidden="true"
        />
      </RouterLink>
      <h1 class="min-w-0 flex-1 text-2xl break-words">
        {{ t('summary.title') }}
      </h1>
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
    <SummaryContent
      v-else-if="trip && summary"
      :trip="trip"
      :summary="summary"
      :currency="trip.currency"
    />
    <BottomNav
      v-if="trip"
      :trip-id="trip.id"
      :labels="navLabels"
      :short-labels="navShortLabels"
      :can-add="!trip.closed && !trip.locked"
      @add="addExpense"
    />
  </main>
</template>
