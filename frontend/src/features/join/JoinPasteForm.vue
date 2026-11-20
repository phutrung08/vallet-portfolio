<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import TextField from '@/components/TextField.vue'

const emit = defineEmits<{ submit: [raw: string] }>()
defineProps<{ rejected: boolean }>()

const { t } = useI18n()
const text = ref('')

function submit(): void {
  emit('submit', text.value)
}
</script>

<template>
  <form
    class="flex flex-col gap-4"
    novalidate
    @submit.prevent="submit"
  >
    <h1 class="text-2xl">
      {{ t('join.pasteTitle') }}
    </h1>
    <p>{{ t('join.pasteBody') }}</p>
    <TextField
      v-model="text"
      :label="t('join.pasteLabel')"
      :placeholder="t('join.pastePlaceholder')"
      :error="rejected ? t('join.pasteInvalid') : undefined"
    />
    <BaseButton
      type="submit"
      variant="dark"
      block
    >
      {{ t('join.pasteContinue') }}
    </BaseButton>
  </form>
</template>
