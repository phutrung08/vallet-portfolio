<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { ChevronLeft, Plus, Settings, Share2 } from 'lucide-vue-next'
import AppWordmark from '@/components/AppWordmark.vue'
import BasePill from '@/components/BasePill.vue'
import { useDesktopBarContext } from '@/lib/desktopBarContext'

const { t } = useI18n()
const route = useRoute()
const trip = useDesktopBarContext()
</script>

<template>
  <header class="desktop-top-bar bg-surface border-edge sticky top-0 z-30 hidden h-14 shrink-0 border-b-[1.5px] desktop:flex">
    <div class="mx-auto flex w-full max-w-[82rem] items-center justify-between gap-4 px-5">
      <div class="flex min-w-0 items-center gap-3">
        <RouterLink
          to="/"
          class="shrink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        >
          <AppWordmark class="text-xl" />
        </RouterLink>
        <RouterLink
          v-if="route.path !== '/'"
          to="/"
          class="bg-sand ink-border rounded-pill text-ink inline-flex shrink-0 items-center gap-1 px-3 py-1 text-xs font-semibold hover:bg-cream focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        >
          <ChevronLeft
            :size="14"
            aria-hidden="true"
          />
          <span>{{ t('desktopBar.trips') }}</span>
        </RouterLink>
        <div
          v-if="trip"
          class="flex min-w-0 items-center gap-2"
        >
          <span class="font-heading text-ink truncate text-base font-semibold">{{ trip.name }}</span>
          <span class="text-muted shrink-0 text-xs">{{ t('trips.members', { n: trip.memberCount }) }}</span>
          <BasePill
            v-if="trip.closed"
            tone="yellow"
          >
            {{ t('trips.status.closed') }}
          </BasePill>
          <BasePill
            v-else-if="trip.readonly"
            tone="yellow"
          >
            {{ t('desktopBar.demo') }}
          </BasePill>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <RouterLink
          v-if="route.path === '/'"
          to="/trips/new"
          class="ink-border rounded-pill shadow-hard-sm bg-green text-on-green inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold transition-colors hover:bg-green-dark focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        >
          <Plus
            :size="14"
            aria-hidden="true"
          />
          <span>{{ t('desktopBar.newTrip') }}</span>
        </RouterLink>
        <RouterLink
          v-if="trip && !trip.readonly"
          :to="`/trips/${encodeURIComponent(trip.id)}/members`"
          class="ink-border rounded-pill bg-surface text-ink inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold hover:bg-sand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        >
          <Share2
            :size="14"
            aria-hidden="true"
          />
          <span>{{ t('trip.share') }}</span>
        </RouterLink>
        <RouterLink
          v-if="route.path !== '/settings'"
          to="/settings"
          :aria-label="t('nav.settings')"
          class="ink-border bg-surface text-ink inline-flex size-9 items-center justify-center rounded-full hover:bg-sand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        >
          <Settings
            :size="17"
            aria-hidden="true"
          />
        </RouterLink>
      </div>
    </div>
  </header>
</template>
