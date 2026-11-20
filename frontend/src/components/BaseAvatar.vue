<script setup lang="ts">
import { computed } from 'vue'

type Size = 'sm' | 'md' | 'lg'
type Tone = 'green' | 'yellow' | 'sky' | 'sand'

const props = withDefaults(
  defineProps<{ name: string; size?: Size; tone?: Tone; muted?: boolean }>(),
  { size: 'md', tone: 'green', muted: false },
)

const sizeClass: Record<Size, string> = { sm: 'size-6', md: 'size-7', lg: 'size-[34px]' }
const toneClass: Record<Tone, string> = {
  green: 'bg-green-soft',
  yellow: 'bg-yellow-soft',
  sky: 'bg-sky-soft',
  sand: 'bg-sand',
}

const segmenter = new Intl.Segmenter(undefined, { granularity: 'grapheme' })
const label = computed(() => props.name.trim())
const initial = computed(() => {
  const first = segmenter.segment(label.value)[Symbol.iterator]().next()
  return first.done ? '?' : first.value.segment.toLocaleUpperCase()
})
</script>

<template>
  <span
    role="img"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : 'true'"
    class="rounded-pill inline-flex shrink-0 items-center justify-center border-[1.5px] text-[11px] font-medium"
    :class="[
      sizeClass[size],
      muted ? 'border-line bg-sand text-muted' : ['border-edge text-ink', toneClass[tone]],
    ]"
  >
    {{ initial }}
  </span>
</template>
