<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'

withDefaults(defineProps<{ message: string; canRetry?: boolean }>(), { canRetry: true })
defineEmits<{ retry: [] }>()

const { t } = useI18n()
</script>

<template>
  <div
    role="alert"
    class="card-ink bg-surface flex flex-col items-start gap-3 p-4"
  >
    <p>{{ message }}</p>
    <BaseButton
      v-if="canRetry"
      variant="outline"
      @click="$emit('retry')"
    >
      {{ t('common.retry') }}
    </BaseButton>
  </div>
</template>
