<script setup lang="ts">
import { ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown } from 'lucide-vue-next'
import TextField from '@/components/TextField.vue'

const note = defineModel<string>('note', { required: true })
const place = defineModel<string>('place', { required: true })
defineProps<{ noteError?: string; placeError?: string }>()

const { t } = useI18n()
const id = useId()
// Keeps the form compact initially unless editing an expense with existing note or place.
const open = ref(note.value !== '' || place.value !== '')
</script>

<template>
  <div class="flex flex-col gap-3">
    <button
      type="button"
      :aria-expanded="open"
      :aria-controls="`${id}-fields`"
      class="flex min-h-11 items-center gap-1 self-start text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      @click="open = !open"
    >
      {{ t('expenseForm.moreFields') }}
      <ChevronDown
        :size="16"
        class="transition-transform motion-reduce:transition-none"
        :class="open && 'rotate-180'"
        aria-hidden="true"
      />
    </button>
    <div
      v-show="open"
      :id="`${id}-fields`"
      class="flex flex-col gap-3"
    >
      <div class="flex flex-col gap-1.5">
        <label
          :for="`${id}-note`"
          class="text-sm font-medium"
        >{{ t('expenseForm.note') }}</label>
        <textarea
          :id="`${id}-note`"
          v-model="note"
          rows="3"
          :aria-invalid="noteError ? 'true' : undefined"
          :aria-describedby="noteError ? `${id}-note-error` : undefined"
          class="ink-border rounded-card bg-surface text-ink w-full px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
          :class="noteError && 'border-danger'"
        />
        <p
          v-if="noteError"
          :id="`${id}-note-error`"
          role="alert"
          class="text-danger text-sm"
        >
          {{ noteError }}
        </p>
      </div>
      <TextField
        v-model="place"
        :label="t('expenseForm.place')"
        :placeholder="t('expenseForm.placePlaceholder')"
        :error="placeError"
      />
    </div>
  </div>
</template>
