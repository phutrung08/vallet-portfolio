<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import SegmentedControl from '@/components/SegmentedControl.vue'

export type BalanceTab = 'transfers' | 'members'

const model = defineModel<BalanceTab>({ required: true })

const { t } = useI18n()
const options = computed(() =>
  (['transfers', 'members'] as const).map((tab) => ({
    value: tab,
    label: t(`balances.tabs.${tab}`),
  })),
)
</script>

<template>
  <SegmentedControl
    v-model="model"
    :label="t('balances.tabs.label')"
    :options="options"
  />
</template>
