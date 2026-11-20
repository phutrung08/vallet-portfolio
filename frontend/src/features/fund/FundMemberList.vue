<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check } from 'lucide-vue-next'
import BaseAvatar from '@/components/BaseAvatar.vue'
import BasePill from '@/components/BasePill.vue'
import type { FundDetail, TripDetail } from '@/entities'
import { memberTotals } from '@/features/fund/fundRules'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{ trip: TripDetail; fund: FundDetail }>()

const { t } = useI18n()
const money = useMoney(() => props.trip.currency)
const rows = computed(() => memberTotals(props.trip, props.fund))
</script>

<template>
  <section class="flex flex-col gap-2">
    <div class="flex items-baseline justify-between gap-2">
      <h2 class="text-lg">
        {{ t('fund.paidTitle') }}
      </h2>
      <p class="font-medium tabular-nums">
        {{ money(fund.contributed) }}
      </p>
    </div>
    <ul class="flex flex-col gap-1">
      <li
        v-for="row in rows"
        :key="row.member.id"
        class="flex min-h-11 items-center gap-3"
      >
        <BaseAvatar :name="row.member.display_name" />
        <span class="min-w-0 flex-1 break-words">{{ row.member.display_name }}</span>
        <BasePill v-if="row.contributed === 0">
          {{ t('fund.notPaid') }}
        </BasePill>
        <template v-else>
          <span class="font-medium tabular-nums">{{ money(row.contributed) }}</span>
          <Check
            :size="18"
            class="text-green-ink"
            aria-hidden="true"
          />
        </template>
      </li>
    </ul>
  </section>
</template>
