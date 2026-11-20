<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import { errorMessageKey } from '@/lib/errors'

/** Fixed-copy confirmation sheet paired with `useDeleteExpense`. */
defineProps<{ open: boolean; pending: boolean; error: unknown }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()

const { t } = useI18n()
</script>

<template>
  <ConfirmSheet
    :open="open"
    danger
    :title="t('expense.deleteTitle')"
    :message="t('expense.deleteBody')"
    :confirm-label="t('expense.deleteConfirm')"
    :pending="pending"
    :error="error ? t(errorMessageKey(error)) : undefined"
    @confirm="emit('confirm')"
    @cancel="emit('cancel')"
  />
</template>
