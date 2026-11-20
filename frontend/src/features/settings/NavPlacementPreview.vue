<script setup lang="ts">
import { computed } from 'vue'
import type { PhonePlacement, WidePlacement } from '@/lib/useNavPlacement'

const props = defineProps<{ kind: 'phone' | 'wide'; value: PhonePlacement | WidePlacement }>()

const LAYOUTS: Record<PhonePlacement | WidePlacement, { bar: string; content: string }> = {
  'bottom-left': { bar: 'bottom-2 left-2 h-4 w-14 flex-row', content: 'pb-8' },
  'bottom-center': { bar: 'inset-x-0 bottom-2 mx-auto h-4 w-14 flex-row', content: 'pb-8' },
  'bottom-right': { bar: 'right-2 bottom-2 h-4 w-14 flex-row', content: 'pb-8' },
  'edge-left': { bar: 'top-1/2 left-2 h-20 w-4 -translate-y-1/2 flex-col', content: 'pl-8' },
  'edge-right': { bar: 'top-1/2 right-2 h-20 w-4 -translate-y-1/2 flex-col', content: 'pr-8' },
  'rail-left': { bar: 'inset-y-2 left-2 w-4 flex-col', content: 'pl-8' },
  'rail-right': { bar: 'inset-y-2 right-2 w-4 flex-col', content: 'pr-8' },
}

const layout = computed(() => LAYOUTS[props.value])
const frame = computed(() => (props.kind === 'phone' ? 'h-[200px] w-[140px]' : 'h-[150px] w-[220px]'))
</script>

<template>
  <div
    aria-hidden="true"
    data-testid="nav-preview"
    :data-value="value"
    class="ink-border bg-cream relative self-center overflow-hidden rounded-2xl"
    :class="frame"
  >
    <div
      class="flex h-full flex-col gap-2 p-2"
      :class="layout.content"
    >
      <div class="bg-line h-3 w-2/3 rounded-full" />
      <div class="bg-line h-8 rounded-lg" />
      <div class="bg-line h-3 w-1/2 rounded-full" />
    </div>
    <div
      class="bg-surface ink-border rounded-pill absolute flex items-center justify-evenly"
      :class="layout.bar"
    >
      <span
        v-for="dot in 4"
        :key="dot"
        class="bg-ink size-1.5 rounded-full"
      />
    </div>
  </div>
</template>
