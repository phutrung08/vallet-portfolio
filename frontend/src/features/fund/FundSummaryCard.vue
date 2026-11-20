<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import type { FundDetail, TripDetail } from '@/entities'
import { useMoney } from '@/lib/useMoney'

const props = defineProps<{ trip: TripDetail; fund: FundDetail }>()

const { t } = useI18n()
const money = useMoney(() => props.trip.currency)
const holderName = computed(
  () => props.trip.members.find((member) => member.id === props.fund.holder_id)?.display_name ?? '',
)
</script>

<template>
  <BaseCard
    tone="yellow"
    class="flex flex-col gap-1 p-4"
  >
    <p class="text-sm font-medium">
      {{ t('fund.remaining') }}
    </p>
    <p class="font-heading text-4xl leading-none font-semibold break-words tabular-nums">
      {{ money(fund.remaining) }}
    </p>
    <p class="text-sm break-words">
      {{ t('fund.holder', { name: holderName }) }}
    </p>
  </BaseCard>
</template>
