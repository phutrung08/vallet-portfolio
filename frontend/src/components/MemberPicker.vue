<script setup lang="ts">
import { Check } from 'lucide-vue-next'
import BaseAvatar from '@/components/BaseAvatar.vue'

export interface PickerOption {
  id: string
  name: string
  /** Optional secondary hint beneath the member name (e.g. already joined). */
  hint?: string
}

const model = defineModel<string | null>({ required: true })
defineProps<{ options: readonly PickerOption[]; label: string }>()
</script>

<template>
  <ul
    role="group"
    :aria-label="label"
    class="grid grid-cols-2 gap-2"
  >
    <li
      v-for="option in options"
      :key="option.id"
    >
      <button
        type="button"
        :aria-pressed="option.id === model"
        class="ink-border rounded-card bg-surface flex min-h-12 w-full items-center gap-2 px-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky aria-pressed:bg-green-soft"
        @click="model = option.id"
      >
        <BaseAvatar :name="option.name" />
        <span class="min-w-0 flex-1">
          <span class="block font-medium break-words">{{ option.name }}</span>
          <span
            v-if="option.hint"
            class="text-muted block text-xs"
          >{{ option.hint }}</span>
        </span>
        <Check
          v-if="option.id === model"
          :size="18"
          class="shrink-0"
          aria-hidden="true"
        />
      </button>
    </li>
  </ul>
</template>
