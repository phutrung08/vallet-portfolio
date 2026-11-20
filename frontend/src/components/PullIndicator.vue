<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RefreshCw } from 'lucide-vue-next'

const props = defineProps<{ offset: number; armed: boolean; refreshing: boolean }>()

const { t } = useI18n()
const REFRESHING_OFFSET = 48
const style = computed(() => ({
  transform: `translateY(${props.refreshing ? REFRESHING_OFFSET : props.offset}px)`,
}))
</script>

<template>
  <p
    role="status"
    class="sr-only"
  >
    {{ refreshing ? t('common.refreshing') : '' }}
  </p>
  <div
    v-if="offset > 0 || refreshing"
    aria-hidden="true"
    data-pull-indicator
    class="pointer-events-none fixed inset-x-0 -top-10 z-30 flex justify-center"
    :style="style"
  >
    <span class="card-ink bg-surface flex size-10 items-center justify-center rounded-full">
      <RefreshCw
        :size="20"
        :class="[armed || refreshing ? 'text-green-ink' : 'text-muted', refreshing && 'motion-safe:animate-spin']"
        :style="refreshing ? undefined : { transform: `rotate(${offset * 3}deg)` }"
      />
    </span>
  </div>
</template>
