<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseAvatar from '@/components/BaseAvatar.vue'
import BaseCard from '@/components/BaseCard.vue'
import type { MemberStanding, TripDetail } from '@/entities'
import PersonName from '@/features/balances/PersonName.vue'
import { percentsOf } from '@/features/summary/summaryRules'
import { useMoney } from '@/lib/useMoney'

/** Shows how much each member paid out of pocket, ordered largest first, alongside their share. */
const props = defineProps<{ trip: TripDetail; standings: readonly MemberStanding[] }>()

const { t } = useI18n()
const money = useMoney(() => props.trip.currency)
const rows = computed(() => {
  // Departed members appear only if they paid toward trip expenses.
  const shown = props.standings.filter((standing) => !standing.removed || standing.paid > 0)
  const sorted = [...shown].sort((a, b) => b.paid - a.paid)
  const percents = percentsOf(sorted.map((standing) => standing.paid))
  return sorted.map((standing, index) => ({ standing, percent: percents[index] ?? 0 }))
})
const nameOf = (id: string) => props.trip.members.find((member) => member.id === id)?.display_name ?? ''
</script>

<template>
  <BaseCard
    class="flex flex-col gap-3 p-4"
    as="section"
  >
    <h2 class="text-lg">
      {{ t('stats.paidBy') }}
    </h2>
    <ul class="flex flex-col gap-3">
      <li
        v-for="{ standing, percent } in rows"
        :key="standing.member_id"
        class="flex items-start gap-3"
      >
        <BaseAvatar
          :name="nameOf(standing.member_id)"
          class="mt-0.5"
        />
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline justify-between gap-2">
            <PersonName
              :trip="trip"
              :member-id="standing.member_id"
              class="min-w-0 font-medium"
            />
            <span class="font-medium tabular-nums">{{ money(standing.paid) }}</span>
          </div>
          <div
            role="img"
            :aria-label="t('summary.percent', { n: percent })"
            class="ink-border mt-1 h-3 overflow-hidden rounded-full"
          >
            <div
              class="bg-green h-full"
              :style="{ width: `${percent}%` }"
            />
          </div>
          <p class="text-muted mt-0.5 text-sm tabular-nums">
            {{ t('stats.share', { amount: money(standing.share) }) }}
          </p>
        </div>
      </li>
    </ul>
  </BaseCard>
</template>
