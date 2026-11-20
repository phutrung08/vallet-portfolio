<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import type { CurrencyCode } from '@/lib/format'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{ total: number; expenseCount: number; currency: CurrencyCode }>()

const { t } = useI18n()
const money = useMoney(() => props.currency)
</script>

<template>
  <BaseCard
    tone="green"
    class="flex flex-col gap-1 p-4"
  >
    <p class="text-sm font-medium">
      {{ t('summary.total') }}
    </p>
    <p class="font-heading text-4xl leading-none font-semibold break-words tabular-nums">
      {{ money(total) }}
    </p>
    <p class="text-sm">
      {{ t('summary.expenseCount', { n: expenseCount }) }}
    </p>
  </BaseCard>
</template>
