<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import BaseCard from '@/components/BaseCard.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import ActivityRow from '@/features/activity/ActivityRow.vue'
import { useActivity } from '@/features/activity/useActivity'
import { ApiError } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'

const { t } = useI18n()
const route = useRoute()
const tripId = computed(() => String(route.params.tripId))
const activity = useActivity(() => tripId.value)
watch(tripId, activity.reload)
const notFound = computed(
  () => activity.error.value instanceof ApiError && activity.error.value.code === 'not_found',
)
</script>

<template>
  <main class="col-center flex min-h-dvh flex-col gap-4 p-4 pb-28">
    <header class="flex items-center gap-1">
      <RouterLink
        :to="`/trips/${encodeURIComponent(tripId)}/members`"
        :aria-label="t('trip.back')"
        class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      >
        <ChevronLeft
          :size="22"
          aria-hidden="true"
        />
      </RouterLink>
      <h1 class="min-w-0 flex-1 text-2xl break-words">
        {{ t('activity.title') }}
      </h1>
    </header>

    <div
      v-if="activity.status.value === 'loading'"
      aria-busy="true"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
      <div class="card-ink bg-sand h-36 animate-pulse motion-reduce:animate-none" />
    </div>
    <ErrorNotice
      v-else-if="activity.status.value === 'error'"
      :message="t(errorMessageKey(activity.error.value))"
      :can-retry="!notFound"
      @retry="activity.reload"
    />
    <template v-else-if="activity.trip.value">
      <p
        v-if="activity.events.value.length === 0"
        class="text-muted text-center"
      >
        {{ t('activity.empty') }}
      </p>
      <BaseCard
        v-else
        as="ul"
        class="!p-0"
      >
        <ActivityRow
          v-for="event in activity.events.value"
          :key="event.id"
          :event="event"
          :trip="activity.trip.value"
        />
      </BaseCard>
      <ErrorNotice
        v-if="activity.moreError.value"
        :message="t(errorMessageKey(activity.moreError.value))"
        @retry="activity.loadMore"
      />
      <BaseButton
        v-else-if="activity.hasMore.value"
        variant="outline"
        block
        :disabled="activity.loadingMore.value"
        @click="activity.loadMore"
      >
        {{ activity.loadingMore.value ? t('common.loading') : t('activity.more') }}
      </BaseButton>
    </template>
  </main>
</template>
