<script setup lang="ts">
import { computed } from 'vue'
import { create } from 'qrcode'

const props = withDefaults(defineProps<{ value: string; size?: number; label?: string }>(), {
  size: 224,
  label: undefined,
})

/** White quiet zone modules required around the matrix for reliable camera detection. */
const QUIET_ZONE = 4

const matrix = computed(() => {
  const { modules } = create(props.value, { errorCorrectionLevel: 'M' })
  const cells: { x: number; y: number }[] = []
  for (let y = 0; y < modules.size; y++) {
    for (let x = 0; x < modules.size; x++) {
      if (modules.get(y, x)) cells.push({ x: x + QUIET_ZONE, y: y + QUIET_ZONE })
    }
  }
  return { cells, extent: modules.size + QUIET_ZONE * 2 }
})
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :viewBox="`0 0 ${matrix.extent} ${matrix.extent}`"
    :width="size"
    :height="size"
    shape-rendering="crispEdges"
    role="img"
    :aria-label="label"
    :aria-hidden="label ? undefined : 'true'"
  >
    <rect
      width="100%"
      height="100%"
      class="fill-white"
    />
    <rect
      v-for="cell in matrix.cells"
      :key="`${cell.x}-${cell.y}`"
      :x="cell.x"
      :y="cell.y"
      width="1"
      height="1"
      class="fill-qr-dark"
    />
  </svg>
</template>
