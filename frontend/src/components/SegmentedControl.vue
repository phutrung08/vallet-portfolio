<script setup lang="ts" generic="T extends string">
defineProps<{ label: string; options: { value: T; label: string }[] }>()

const model = defineModel<T>({ required: true })
</script>

<template>
  <div
    role="group"
    :aria-label="label"
    class="ink-border rounded-pill bg-surface flex gap-1 p-1"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      :aria-pressed="model === option.value"
      class="rounded-pill min-h-11 flex-1 px-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky aria-pressed:bg-ink aria-pressed:text-on-accent"
      @click="model = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>
