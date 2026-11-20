<script setup lang="ts">
import { computed, provide } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, RouterView } from 'vue-router'
import { demoSource } from '@/features/demo/demoSource'
import { tripSourceKey } from '@/lib/tripSource'

provide(tripSourceKey, demoSource)

const { t } = useI18n()
const isDemoOnly = computed(() => import.meta.env.VITE_DEMO_ONLY === 'true')
</script>

<template>
  <div class="bg-yellow-soft border-edge border-b-[1.5px]">
    <div class="mx-auto flex max-w-md items-center justify-between gap-3 px-4 py-2">
      <p class="min-w-0 text-sm font-medium">
        {{ t('demo.banner') }}
      </p>
      <RouterLink
        v-if="!isDemoOnly"
        :to="{ name: 'create-trip' }"
        class="ink-border rounded-pill bg-ink text-on-accent inline-flex min-h-11 shrink-0 items-center px-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      >
        {{ t('demo.create') }}
      </RouterLink>
    </div>
  </div>
  <RouterView />
</template>
