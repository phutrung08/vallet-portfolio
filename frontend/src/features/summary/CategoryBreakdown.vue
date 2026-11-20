<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import type { CategoryBreakdown } from '@/entities'
import { categoryIcons } from '@/features/expenses/categoryIcons'
import { categoryColors } from '@/features/summary/categoryColors'
import type { CurrencyCode } from '@/lib/format'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{ categories: readonly CategoryBreakdown[]; currency: CurrencyCode }>()

const { t } = useI18n()
const money = useMoney(() => props.currency)
const name = (share: CategoryBreakdown) => t(`expenseForm.categories.${share.category}`)
const summary = computed(() =>
  props.categories
    .map((share) => `${name(share)} ${t('summary.percent', { n: share.percent })}`)
    .join(', '),
)
</script>

<template>
  <BaseCard
    class="flex flex-col gap-3 p-4"
    as="section"
  >
    <h2 class="text-lg">
      {{ t('summary.byCategory') }}
    </h2>
    <div
      role="img"
      :aria-label="summary"
      class="ink-border flex h-5 overflow-hidden rounded-full"
    >
      <div
        v-for="share in categories"
        :key="share.category"
        class="border-edge h-full border-r-[1.5px] last:border-r-0"
        :class="categoryColors[share.category]"
        :style="{ width: `${share.percent}%` }"
      />
    </div>
    <ul class="flex flex-col gap-1">
      <li
        v-for="share in categories"
        :key="share.category"
        class="flex min-h-9 items-center gap-2"
      >
        <span
          class="ink-border size-3 shrink-0 rounded-full"
          :class="categoryColors[share.category]"
          aria-hidden="true"
        />
        <component
          :is="categoryIcons[share.category]"
          :size="16"
          class="shrink-0"
          aria-hidden="true"
        />
        <span class="min-w-0 flex-1 break-words">{{ name(share) }}</span>
        <span class="font-medium tabular-nums">{{ money(share.amount) }}</span>
        <span class="text-muted w-10 text-right text-sm tabular-nums">{{
          t('summary.percent', { n: share.percent })
        }}</span>
      </li>
    </ul>
  </BaseCard>
</template>
