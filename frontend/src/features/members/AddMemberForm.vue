<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import TextField from '@/components/TextField.vue'

const text = defineModel<string>({ required: true })
defineProps<{ errorKey: string | null; pending: boolean }>()
defineEmits<{ submit: [] }>()

const { t } = useI18n()
</script>

<template>
  <form
    class="flex items-start gap-2"
    novalidate
    @submit.prevent="$emit('submit')"
  >
    <TextField
      v-model="text"
      class="flex-1"
      :label="t('members.addLabel')"
      :placeholder="t('members.addPlaceholder')"
      :error="errorKey ? t(errorKey) : undefined"
    />
    <BaseButton
      type="submit"
      variant="outline"
      class="mt-7"
      :disabled="pending"
    >
      {{ t('members.addButton') }}
    </BaseButton>
  </form>
</template>
