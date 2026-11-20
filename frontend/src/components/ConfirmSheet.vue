<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import BottomSheet from '@/components/BottomSheet.vue'

withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel: string
    cancelLabel?: string
    danger?: boolean
    pending?: boolean
    error?: string
  }>(),
  { cancelLabel: undefined, danger: false, pending: false, error: undefined },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()

const { t } = useI18n()
</script>

<template>
  <BottomSheet
    :open="open"
    :title="title"
    @close="emit('cancel')"
  >
    <p class="mb-4">
      {{ message }}
    </p>
    <p
      v-if="error"
      role="alert"
      class="text-danger mb-3 text-sm"
    >
      {{ error }}
    </p>
    <div class="flex flex-col gap-2">
      <BaseButton
        :variant="danger ? 'danger' : 'primary'"
        block
        :disabled="pending"
        @click="emit('confirm')"
      >
        {{ confirmLabel }}
      </BaseButton>
      <BaseButton
        variant="outline"
        block
        :autofocus="danger || undefined"
        :disabled="pending"
        @click="emit('cancel')"
      >
        {{ cancelLabel ?? t('common.cancel') }}
      </BaseButton>
    </div>
  </BottomSheet>
</template>
