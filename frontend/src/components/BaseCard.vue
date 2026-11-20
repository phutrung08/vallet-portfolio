<script setup lang="ts">
type Tone = 'surface' | 'green' | 'yellow' | 'sky' | 'sand'

withDefaults(
  defineProps<{
    tone?: Tone
    flat?: boolean
    as?: string
  }>(),
  { tone: 'surface', flat: false, as: 'div' },
)

const toneClass: Record<Tone, string> = {
  surface: 'bg-surface text-ink',
  green: 'bg-green text-on-green',
  yellow: 'bg-yellow-soft text-ink',
  sky: 'bg-sky-soft text-ink',
  sand: 'bg-sand text-ink',
}
</script>

<template>
  <component
    :is="as"
    class="ink-border rounded-card p-3"
    :class="[toneClass[tone], !flat && 'shadow-hard']"
  >
    <slot />
  </component>
</template>
