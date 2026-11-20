<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import BottomNav from '@/components/BottomNav.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import SplitLayout from '@/components/SplitLayout.vue'
import type { TripDetail } from '@/entities'
import { useAddExpense } from '@/features/expenses/useAddExpense'
import MembersContent from '@/features/members/MembersContent.vue'
import MembersDetailPane from '@/features/members/MembersDetailPane.vue'
import { useMemberSelection } from '@/features/members/useMemberSelection'
import { useShareLink } from '@/features/members/useShareLink'
import { ApiError, api } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useAsyncData } from '@/lib/useAsyncData'
import { useNavLabels } from '@/lib/useNavLabels'
import { useSplit } from '@/lib/useSplit'

const { t } = useI18n()
const route = useRoute()
const tripId = computed(() => String(route.params.tripId))
const { data: trip, status, error, reload, refresh } = useAsyncData((signal) =>
  api.get<TripDetail>(`/trips/${encodeURIComponent(tripId.value)}`, { signal }),
)
watch(tripId, reload)
const share = useShareLink(
  () => tripId.value,
  () => trip.value?.name ?? '',
  () => t('members.invite.shareText', { name: trip.value?.name ?? '' }),
)
const split = useSplit()
const selection = useMemberSelection(split, () => trip.value)
const navLabels = useNavLabels()

const addExpense = useAddExpense(() => tripId.value)
</script>

<template>
  <SplitLayout>
    <template #list>
      <header class="flex items-center gap-1">
        <RouterLink
          :to="`/trips/${encodeURIComponent(tripId)}`"
          :aria-label="t('trip.back')"
          class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        >
          <ChevronLeft
            :size="22"
            aria-hidden="true"
          />
        </RouterLink>
        <h1 class="min-w-0 flex-1 text-2xl break-words">
          {{ t('members.title') }}
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
      <MembersContent
        v-else-if="trip"
        :trip="trip"
        :share="share"
        :split="split"
        :selected-id="selection.selected.value?.id ?? null"
        :refresh="refresh"
        @select="selection.select"
      />
    </template>
    <template #detail>
      <MembersDetailPane
        v-if="split && trip"
        :trip="trip"
        :member="selection.selected.value"
        :share="share"
        :refresh="refresh"
        @close="selection.select(null)"
      />
    </template>
  </SplitLayout>
  <BottomNav
    v-if="trip"
    :trip-id="trip.id"
    :labels="navLabels"
    @add="addExpense"
  />
</template>
