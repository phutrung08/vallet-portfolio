<script setup lang="ts">
type Tone = 'neutral' | 'green' | 'yellow' | 'sky' | 'danger'

withDefaults(defineProps<{ tone?: Tone; selected?: boolean }>(), {
  tone: 'neutral',
  selected: false,
})

const toneClass: Record<Tone, string> = {
  neutral: 'bg-surface text-muted',
  green: 'bg-green-soft text-green-ink',
  yellow: 'bg-yellow-soft text-ink',
  sky: 'bg-sky-soft text-ink',
  danger: 'bg-danger-soft text-danger',
}
</script>

<template>
  <span
    class="rounded-pill inline-block px-2.5 py-1 text-xs whitespace-nowrap"
    :class="selected ? 'ink-border bg-ink text-on-accent' : toneClass[tone]"
  >
    <slot />
  </span>
</template>
