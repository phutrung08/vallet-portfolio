<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { Settings } from 'lucide-vue-next'
import AppWordmark from '@/components/AppWordmark.vue'
import CachedNotice from '@/components/CachedNotice.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import PullIndicator from '@/components/PullIndicator.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SplitLayout from '@/components/SplitLayout.vue'
import type { TripSummary } from '@/entities'
import HomeEmptyState from '@/features/trips/HomeEmptyState.vue'
import TripList from '@/features/trips/TripList.vue'
import TripOverviewPane from '@/features/trips/TripOverviewPane.vue'
import { localIsoDate } from '@/features/trips/tripMeta'
import { useTripList } from '@/features/trips/useTripList'
import { useTripSelection } from '@/features/trips/useTripSelection'
import { errorMessageKey } from '@/lib/errors'
import { usePullToRefresh } from '@/lib/usePullToRefresh'
import { useSplit } from '@/lib/useSplit'

// Clock prop lets tests pin "today" deterministically; production routes use the system clock.
const props = withDefaults(defineProps<{ now?: () => Date }>(), { now: () => new Date() })

const { t } = useI18n()
const router = useRouter()
const { trips, status, error, cachedCopy, reload, refresh } = useTripList()
const layout = useTemplateRef('layout')
const pull = usePullToRefresh(computed(() => layout.value?.listPane ?? null), refresh)
// Above the split breakpoint, the selected trip renders its overview in the detail pane.
const split = useSplit()
const selection = useTripSelection(split, () => trips.value)
const today = computed(() => localIsoDate(props.now()))

const settingsLink =
  '-mr-2 flex size-11 items-center justify-center rounded-full text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky'

function createTrip(): void {
  void router.push('/trips/new')
}

function openTrip(trip: TripSummary): void {
  void router.push(`/trips/${encodeURIComponent(trip.id)}`)
}

// Tapping the already-selected trip opens it; tapping any other trip selects its overview first.
function pick(trip: TripSummary): void {
  if (trip.id === selection.selected.value?.id) openTrip(trip)
  else void selection.select(trip)
}
</script>

<template>
  <SplitLayout
    ref="layout"
    :nav="false"
  >
    <template #list>
      <PullIndicator
        :offset="pull.offset.value"
        :armed="pull.armed.value"
        :refreshing="pull.refreshing.value"
      />
      <header class="flex items-center gap-1">
        <AppWordmark class="mr-auto" />
        <RefreshButton
          :refreshing="pull.refreshing.value"
          @refresh="pull.refresh"
        />
        <RouterLink
          to="/settings"
          :aria-label="t('nav.settings')"
          :class="settingsLink"
        >
          <Settings
            :size="22"
            aria-hidden="true"
          />
        </RouterLink>
      </header>

      <div
        v-if="status === 'loading'"
        aria-busy="true"
        class="flex flex-col gap-3"
      >
        <span class="sr-only">{{ t('common.loading') }}</span>
        <div
          v-for="n in 2"
          :key="n"
          class="card-ink bg-sand h-20 animate-pulse motion-reduce:animate-none"
        />
      </div>
      <ErrorNotice
        v-else-if="status === 'error'"
        :message="t(errorMessageKey(error))"
        @retry="reload"
      />
      <HomeEmptyState
        v-else-if="trips.length === 0 && !split"
        @create="createTrip"
      />
      <template v-else>
        <CachedNotice :copy="cachedCopy" />
        <TripList
          :trips="trips"
          :today="today"
          :split="split"
          :selected-id="selection.selected.value?.id"
          @create="createTrip"
          @select="pick"
        />
      </template>
    </template>
    <template #detail>
      <template v-if="split && status === 'ready'">
        <TripOverviewPane
          v-if="selection.selected.value"
          :key="selection.selected.value.id"
          :trip="selection.selected.value"
          :today="today"
          @open="openTrip(selection.selected.value)"
        />
        <HomeEmptyState
          v-else
          :create="false"
        />
      </template>
    </template>
  </SplitLayout>
</template>
