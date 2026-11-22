<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import ErrorNotice from '@/components/ErrorNotice.vue'
import FundContent from '@/features/fund/FundContent.vue'
import { useFundPage } from '@/features/fund/useFundPage'
import { localIsoDate } from '@/features/trips/tripMeta'
import { ApiError } from '@/lib/api'
import { useDesktopBarTrip } from '@/lib/desktopBarContext'
import { errorMessageKey } from '@/lib/errors'

// Injectable clock lets tests pin "today" deterministically.
const props = withDefaults(defineProps<{ now?: () => Date }>(), { now: () => new Date() })

const { t } = useI18n()
const route = useRoute()
const tripId = computed(() => String(route.params.tripId))
const { trip, fund, status, error, reload, refresh } = useFundPage(() => tripId.value)
useDesktopBarTrip(() => trip.value)
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
        {{ t('fund.title') }}
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
    <FundContent
      v-else-if="trip"
      :trip="trip"
      :fund="fund"
      :today="localIsoDate(props.now())"
      :refresh="refresh"
    />
  </main>
</template>
