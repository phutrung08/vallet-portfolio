<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'

const { t } = useI18n()
</script>

<template>
  <BaseCard
    as="section"
    class="flex flex-col gap-1 p-4"
  >
    <h2 class="text-xl">
      {{ t('settings.device.title') }}
    </h2>
    <p class="text-sm">
      {{ t('settings.device.body') }}
    </p>
    <p class="text-sm">
      {{ t('settings.device.offline') }}
    </p>
  </BaseCard>
</template>
