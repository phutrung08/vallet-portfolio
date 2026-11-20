<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'

defineProps<{ open: boolean }>()
defineEmits<{ reload: []; close: [] }>()

const { t } = useI18n()
</script>

<template>
  <div
    role="status"
    class="pointer-events-none fixed right-(--nav-reserve-right) bottom-[calc(var(--nav-reserve-bottom)+1rem+env(safe-area-inset-bottom))] left-(--nav-reserve-left) z-40 mx-auto flex max-w-md justify-center px-4 rail:max-w-none"
  >
    <div
      v-if="open"
      class="card-ink bg-surface pointer-events-auto flex items-center gap-2 py-1 pr-1 pl-4 text-sm"
    >
      <span>{{ t('pwa.updateAvailable') }} ·</span>
      <button
        type="button"
        class="text-green-ink min-h-11 rounded-full px-2 font-medium underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        @click="$emit('reload')"
      >
        {{ t('pwa.reload') }}
      </button>
      <button
        type="button"
        :aria-label="t('pwa.later')"
        class="flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        @click="$emit('close')"
      >
        <X
          :size="18"
          aria-hidden="true"
        />
      </button>
    </div>
  </div>
</template>
