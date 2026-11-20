<script setup lang="ts">
import { useId } from 'vue'
import { applyInput, type FieldEvent } from '@/lib/fieldInput'

const model = defineModel<string>({ required: true })

const props = defineProps<{
  label: string
  error?: string
  type?: 'text' | 'date'
  inputmode?: 'numeric' | 'text'
  placeholder?: string
  autocomplete?: string
  /** Optional synchronous value normalizer (e.g. digits only) applied after IME composition ends. */
  normalise?: (raw: string) => string
}>()

const id = useId()

function onInput(event: FieldEvent): void {
  const next = applyInput(event, props.normalise)
  if (next !== null) model.value = next
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label
      :for="id"
      class="text-sm font-medium"
    >{{ label }}</label>
    <input
      :id="id"
      :value="model"
      :type="type ?? 'text'"
      :inputmode="inputmode"
      :placeholder="placeholder"
      :autocomplete="autocomplete ?? 'off'"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-error` : undefined"
      class="ink-border rounded-card bg-surface text-ink min-h-11 w-full px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      :class="error && 'border-danger'"
      @input="onInput"
      @compositionend="onInput"
    >
    <p
      v-if="error"
      :id="`${id}-error`"
      role="alert"
      class="text-danger text-sm"
    >
      {{ error }}
    </p>
  </div>
</template>
