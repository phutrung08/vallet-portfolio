<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseAvatar from '@/components/BaseAvatar.vue'
import type { MemberStanding, TripDetail } from '@/entities'
import PersonName from '@/features/balances/PersonName.vue'
import { coveredPercent } from '@/features/balances/balanceRules'
import { useMoney, useSignedMoney } from '@/lib/useMoney'

const props = defineProps<{ trip: TripDetail; standing: MemberStanding; showPayments: boolean }>()

const { t } = useI18n()
const money = useMoney(() => props.trip.currency)
const signed = useSignedMoney(() => props.trip.currency)
const name = computed(
  () => props.trip.members.find((member) => member.id === props.standing.member_id)?.display_name ?? '',
)
const fronted = computed(() => props.standing.paid + props.standing.contributed)
const percent = computed(() => coveredPercent(fronted.value, props.standing.share))
const netClass = computed(() => {
  if (props.standing.net > 0) return 'text-green-ink'
  return props.standing.net < 0 ? 'text-danger' : 'text-muted'
})
const detail = computed(() => {
  const parts = [`${money(fronted.value)} / ${money(props.standing.share)}`]
  if (props.showPayments && props.standing.sent > 0) {
    parts.push(t('balances.sent', { amount: money(props.standing.sent) }))
  }
  if (props.showPayments && props.standing.received > 0) {
    parts.push(t('balances.received', { amount: money(props.standing.received) }))
  }
  return parts.join(' · ')
})
const barLabel = computed(() =>
  t('balances.coverage', { paid: money(fronted.value), share: money(props.standing.share) }),
)
</script>

<template>
  <li class="flex min-h-14 items-start gap-3 py-1.5">
    <BaseAvatar
      :name="name"
      class="mt-0.5"
    />
    <div class="min-w-0 flex-1">
      <div class="flex items-baseline justify-between gap-2">
        <PersonName
          :trip="trip"
          :member-id="standing.member_id"
          class="font-medium"
        />
        <span
          data-testid="net"
          class="font-medium tabular-nums"
          :class="netClass"
        >{{ signed(standing.net) }}</span>
      </div>
      <p class="text-muted text-xs tabular-nums">
        {{ detail }}
      </p>
      <div
        role="progressbar"
        :aria-label="barLabel"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuenow="percent"
        class="bg-sand mt-1 h-1.5 overflow-hidden rounded-full"
      >
        <div
          class="bg-green h-full rounded-full"
          :style="{ width: `${percent}%` }"
        />
      </div>
    </div>
  </li>
</template>
