<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { ChartPie } from 'lucide-vue-next'

defineProps<{ tripId: string }>()

const { t } = useI18n()
</script>

<template>
  <RouterLink
    :to="`/trips/${encodeURIComponent(tripId)}/summary`"
    class="ink-border rounded-pill shadow-hard bg-surface inline-flex min-h-11 w-full items-center justify-center px-5 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
  >
    <ChartPie
      :size="18"
      class="mr-1.5"
      aria-hidden="true"
    />
    {{ t('summary.link') }}
  </RouterLink>
</template>
