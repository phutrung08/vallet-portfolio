<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { ChevronRight, History } from 'lucide-vue-next'

defineProps<{ tripId: string }>()

const { t } = useI18n()
</script>

<template>
  <RouterLink
    :to="`/trips/${encodeURIComponent(tripId)}/activity`"
    class="card-ink bg-surface flex min-h-11 items-center gap-3 p-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
  >
    <History
      :size="20"
      aria-hidden="true"
    />
    <span class="flex-1 font-medium">{{ t('members.activity') }}</span>
    <ChevronRight
      :size="18"
      aria-hidden="true"
    />
  </RouterLink>
</template>
