<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import type { MemberStanding } from '@/entities'
import { meStatus } from '@/features/balances/balanceRules'
import type { CurrencyCode } from '@/lib/format'
import { useMoney, useSignedMoney } from '@/lib/useMoney'

const props = defineProps<{ standing: MemberStanding; currency: CurrencyCode }>()

const { t } = useI18n()
const money = useMoney(() => props.currency)
const signed = useSignedMoney(() => props.currency)
const status = computed(() => meStatus(props.standing.net))
const detail = computed(() =>
  t('balances.me.detail', {
    paid: money(props.standing.paid + props.standing.contributed),
    share: money(props.standing.share),
  }),
)
</script>

<template>
  <BaseCard
    tone="green"
    class="flex flex-col gap-1 p-4"
  >
    <p class="text-sm font-medium">
      {{ t(`balances.me.${status}`) }}
    </p>
    <p class="font-heading text-4xl leading-none font-semibold break-words tabular-nums">
      {{ signed(standing.net) }}
    </p>
    <p class="text-sm tabular-nums">
      {{ detail }}
    </p>
  </BaseCard>
</template>
