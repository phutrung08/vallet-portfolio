<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'

const { t } = useI18n()
</script>

<template>
  <header class="flex items-center gap-1">
    <RouterLink
      to="/"
      :aria-label="t('settings.back')"
      class="-ml-2 flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
    >
      <ChevronLeft
        :size="22"
        aria-hidden="true"
      />
    </RouterLink>
    <h1 class="min-w-0 flex-1 text-2xl break-words">
      {{ t('settings.title') }}
    </h1>
  </header>
</template>
