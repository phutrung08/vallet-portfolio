<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MemberStanding, TripDetail } from '@/entities'
import MemberBalanceRow from '@/features/balances/MemberBalanceRow.vue'
import { standingsInTripOrder } from '@/features/balances/balanceRules'

const props = defineProps<{
  trip: TripDetail
  standings: readonly MemberStanding[]
  hasPayments: boolean
}>()

const { t } = useI18n()
const rows = computed(() => standingsInTripOrder(props.standings, props.trip.members))
</script>

<template>
  <section class="flex flex-col gap-2">
    <div class="text-muted flex items-baseline justify-between gap-2 text-sm">
      <p>{{ t('balances.frontedCaption') }}</p>
      <p>{{ t('balances.differenceCaption') }}</p>
    </div>
    <ul class="flex flex-col gap-1">
      <MemberBalanceRow
        v-for="standing in rows"
        :key="standing.member_id"
        :trip="trip"
        :standing="standing"
        :show-payments="hasPayments"
      />
    </ul>
  </section>
</template>
