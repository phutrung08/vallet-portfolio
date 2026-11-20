<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'
import BaseAvatar from '@/components/BaseAvatar.vue'
import BaseButton from '@/components/BaseButton.vue'
import TextField from '@/components/TextField.vue'
import { MAX_OTHER_MEMBERS, checkNewMember, type ErrorKey } from '@/features/trips/tripFormRules'

const names = defineModel<string[]>({ required: true })
const props = defineProps<{ creatorName: string; error?: ErrorKey }>()

const { t } = useI18n()
const draft = ref('')
const addError = ref<ErrorKey>()

function add(): void {
  const result = checkNewMember(draft.value, props.creatorName, names.value)
  if ('error' in result) {
    addError.value = result.error
    return
  }
  names.value = [...names.value, result.name]
  draft.value = ''
  addError.value = undefined
}

function remove(index: number): void {
  names.value = names.value.filter((_, position) => position !== index)
}

function message(key: ErrorKey | undefined): string | undefined {
  return key && t(`createTrip.errors.${key}`)
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-start gap-2">
      <TextField
        v-model="draft"
        class="flex-1"
        :label="t('createTrip.others')"
        :placeholder="t('createTrip.othersPlaceholder')"
        :error="message(addError ?? error)"
        @keydown.enter.prevent="add"
      />
      <BaseButton
        variant="outline"
        class="mt-7"
        @click="add"
      >
        {{ t('createTrip.add') }}
      </BaseButton>
    </div>
    <p class="text-muted text-right text-xs">
      {{ t('createTrip.counter', { n: names.length, max: MAX_OTHER_MEMBERS }) }}
    </p>
    <ul class="flex flex-wrap gap-2">
      <li
        v-for="(name, index) in names"
        :key="name"
        class="ink-border rounded-pill bg-surface flex items-center gap-1.5 pl-2 text-sm"
      >
        <BaseAvatar
          :name="name"
          size="sm"
        />
        <span class="break-all">{{ name }}</span>
        <button
          type="button"
          :aria-label="t('createTrip.remove', { name })"
          class="rounded-pill flex min-h-11 min-w-11 items-center justify-center focus-visible:outline-2 focus-visible:outline-sky"
          @click="remove(index)"
        >
          <X
            :size="16"
            aria-hidden="true"
          />
        </button>
      </li>
    </ul>
  </div>
</template>
