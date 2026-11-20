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
    class="flex flex-col gap-4"
    novalidate
    @submit.prevent="$emit('submit')"
  >
    <TextField
      v-model="text"
      :label="t('members.renameLabel')"
      :error="errorKey ? t(errorKey) : undefined"
    />
    <BaseButton
      type="submit"
      variant="success"
      block
      :disabled="pending"
    >
      {{ t('members.renameSave') }}
    </BaseButton>
  </form>
</template>
