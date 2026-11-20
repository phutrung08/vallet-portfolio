<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ErrorNotice from '@/components/ErrorNotice.vue'
import type { TripDetail } from '@/entities'
import { useMemberFacts } from '@/features/members/useMemberFacts'
import { errorMessageKey } from '@/lib/errors'
import { useMoney, useSignedMoney } from '@/lib/useMoney'

/** Displays a member's trip financials (fronted amount, share, net) and masked bank account. */
const props = defineProps<{ trip: TripDetail; memberId: string }>()

const { t } = useI18n()
const money = useMoney(() => props.trip.currency)
const signed = useSignedMoney(() => props.trip.currency)
const facts = useMemberFacts(() => props.trip.id)
const standing = computed(() => facts.data.value?.standings.find((item) => item.member_id === props.memberId))
const account = computed(() => facts.data.value?.accounts.find((item) => item.member_id === props.memberId))
const netClass = computed(() => {
  const net = standing.value?.net ?? 0
  if (net > 0) return 'text-green-ink'
  return net < 0 ? 'text-danger' : 'text-muted'
})
</script>

<template>
  <div
    v-if="facts.status.value === 'loading'"
    aria-busy="true"
  >
    <span class="sr-only">{{ t('common.loading') }}</span>
    <div class="card-ink bg-sand h-36 animate-pulse motion-reduce:animate-none" />
  </div>
  <ErrorNotice
    v-else-if="facts.status.value === 'error'"
    :message="t(errorMessageKey(facts.error.value))"
    @retry="facts.reload"
  />
  <dl
    v-else
    class="card-ink bg-surface flex flex-col gap-2 p-4"
  >
    <template v-if="standing">
      <div class="flex items-baseline justify-between gap-3">
        <dt>{{ t('members.detail.fronted') }}</dt>
        <dd class="font-medium tabular-nums">
          {{ money(standing.paid + standing.contributed) }}
        </dd>
      </div>
      <div class="flex items-baseline justify-between gap-3">
        <dt>{{ t('members.detail.share') }}</dt>
        <dd class="font-medium tabular-nums">
          {{ money(standing.share) }}
        </dd>
      </div>
      <div class="flex items-baseline justify-between gap-3">
        <dt>{{ t('members.detail.net') }}</dt>
        <dd
          class="font-medium tabular-nums"
          :class="netClass"
        >
          {{ signed(standing.net) }}
        </dd>
      </div>
    </template>
    <div class="flex items-baseline justify-between gap-3">
      <dt>{{ t('members.detail.bank') }}</dt>
      <dd class="text-right font-medium break-words">
        {{
          account
            ? `${account.bank_short_name} ${t('balances.qr.last4', { last4: account.account_last4 })}`
            : t('members.detail.noBank')
        }}
      </dd>
    </div>
  </dl>
</template>
