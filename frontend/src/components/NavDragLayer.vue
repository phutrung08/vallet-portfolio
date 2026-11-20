<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DropZone, Rect, ZoneId } from '@/lib/navDropZones'

const props = defineProps<{
  dragging: boolean
  zones: readonly DropZone[]
  target: ZoneId | null
  moved: ZoneId | null
}>()

const { t } = useI18n()
const announcement = computed(() => (props.moved ? t(`nav.moved.${props.moved}`) : ''))

function box(rect: Rect) {
  return { left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px` }
}
</script>

<template>
  <span
    role="status"
    class="sr-only"
  >{{ announcement }}</span>
  <Teleport to="body">
    <div
      v-if="dragging"
      data-testid="nav-drop-zones"
      aria-hidden="true"
      class="pointer-events-none fixed inset-0 z-30"
    >
      <div
        v-for="zone in zones"
        :key="zone.id"
        :data-zone="zone.id"
        :data-active="zone.id === target || undefined"
        class="rounded-card absolute border-2 border-dashed transition-colors duration-100 motion-reduce:transition-none"
        :class="zone.id === target ? 'border-sky bg-sky-soft/70' : 'border-edge/50'"
        :style="box(zone.rect)"
      />
    </div>
  </Teleport>
</template>
