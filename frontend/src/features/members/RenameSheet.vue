<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BottomSheet from '@/components/BottomSheet.vue'
import RenameForm from '@/features/members/RenameForm.vue'

const text = defineModel<string>({ required: true })
defineProps<{ open: boolean; errorKey: string | null; pending: boolean }>()
const emit = defineEmits<{ close: []; submit: [] }>()

const { t } = useI18n()
</script>

<template>
  <BottomSheet
    :open="open"
    :title="t('members.renameTitle')"
    @close="emit('close')"
  >
    <RenameForm
      v-model="text"
      :error-key="errorKey"
      :pending="pending"
      @submit="emit('submit')"
    />
  </BottomSheet>
</template>
