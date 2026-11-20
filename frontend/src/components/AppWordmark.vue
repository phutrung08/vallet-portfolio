<script setup lang="ts">
withDefaults(defineProps<{ size?: 'sm' | 'md' }>(), { size: 'sm' })
</script>

<template>
  <span
    class="font-heading font-semibold lowercase"
    :class="size === 'md' ? 'text-[22px]' : 'text-[17px]'"
  >
    <span class="sr-only">Vallet</span><span
      class="text-ink"
      aria-hidden="true"
    >val</span><span
      class="text-green"
      aria-hidden="true"
    >let</span>
  </span>
</template>
