<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { PartyPopper } from 'lucide-vue-next'
import BaseCard from '@/components/BaseCard.vue'
import type { Transfer, TripDetail } from '@/entities'
import TransferRow from '@/features/balances/TransferRow.vue'
import { transfersMeFirst } from '@/features/balances/balanceRules'
import { transferKey } from '@/features/balances/useTransferSelection'

const props = defineProps<{
  trip: TripDetail
  transfers: readonly Transfer[]
  canPay: boolean
  split: boolean
  selectedKey: string | null
}>()
defineEmits<{ pay: [transfer: Transfer] }>()

const { t } = useI18n()
const rows = computed(() => transfersMeFirst(props.transfers, props.trip.me))
</script>

<template>
  <section class="flex flex-col gap-2">
    <div class="flex items-baseline justify-between gap-2">
      <h2 class="text-lg">
        {{ t('balances.transfersTitle') }}
      </h2>
      <p
        v-if="rows.length > 0"
        class="text-muted text-sm"
      >
        {{ t('balances.transferCount', { n: rows.length }) }}
      </p>
    </div>
    <BaseCard
      v-if="rows.length === 0"
      tone="yellow"
      class="flex flex-col items-center gap-2 p-5 text-center"
    >
      <PartyPopper
        :size="32"
        aria-hidden="true"
      />
      <p class="font-heading text-xl font-semibold">
        {{ t('balances.empty') }}
      </p>
    </BaseCard>
    <ul
      v-else
      class="flex flex-col gap-2"
    >
      <TransferRow
        v-for="row in rows"
        :key="transferKey(row)"
        :trip="trip"
        :transfer="row"
        :can-pay="canPay"
        :split="split"
        :selected="transferKey(row) === selectedKey"
        @pay="$emit('pay', row)"
      />
    </ul>
  </section>
</template>
