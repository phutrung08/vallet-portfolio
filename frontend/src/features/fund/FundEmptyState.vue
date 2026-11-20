<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import BaseCard from '@/components/BaseCard.vue'

defineProps<{ canEdit: boolean; pending: boolean; error: string | null }>()
defineEmits<{ enable: [] }>()

const { t } = useI18n()
</script>

<template>
  <BaseCard
    tone="yellow"
    class="flex flex-col items-start gap-3 p-4"
  >
    <h2 class="text-lg">
      {{ t('fund.emptyTitle') }}
    </h2>
    <p class="text-sm">
      {{ t('fund.emptyBody') }}
    </p>
    <p
      v-if="error"
      role="alert"
      class="text-danger text-sm"
    >
      {{ error }}
    </p>
    <BaseButton
      v-if="canEdit"
      variant="success"
      :disabled="pending"
      @click="$emit('enable')"
    >
      {{ t('fund.turnOn') }}
    </BaseButton>
  </BaseCard>
</template>
