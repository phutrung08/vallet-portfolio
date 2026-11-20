<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { CloudOff } from 'lucide-vue-next'
import { useOnline } from '@/lib/useOnline'

const { t } = useI18n()
const online = useOnline()
</script>

<template>
  <!-- Keep the live region mounted so screen readers announce transitions when connectivity drops. -->
  <div
    role="status"
    class="sticky top-0 z-30"
  >
    <p
      v-if="!online"
      class="bg-yellow-soft text-ink border-edge flex items-center justify-center gap-1.5 border-b-[1.5px] pt-[calc(0.25rem+env(safe-area-inset-top))] pr-[calc(1rem+var(--nav-reserve-right))] pb-1 pl-[calc(1rem+var(--nav-reserve-left))] text-center text-sm"
    >
      <CloudOff
        :size="16"
        aria-hidden="true"
      />
      {{ t('offline.banner') }}
    </p>
  </div>
</template>
