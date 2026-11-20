<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RefreshCw } from 'lucide-vue-next'

defineProps<{ refreshing: boolean }>()
defineEmits<{ refresh: [] }>()

const { t } = useI18n()
</script>

<template>
  <button
    type="button"
    :aria-label="t('common.refresh')"
    :aria-busy="refreshing"
    :disabled="refreshing"
    class="text-ink flex size-11 shrink-0 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky disabled:opacity-60"
    @click="$emit('refresh')"
  >
    <RefreshCw
      :size="22"
      aria-hidden="true"
      :class="refreshing && 'motion-safe:animate-spin'"
    />
  </button>
</template>
