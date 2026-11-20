<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import type { Contribution, FundDetail, TripDetail } from '@/entities'
import ContributionList from '@/features/fund/ContributionList.vue'
import ContributionSheet from '@/features/fund/ContributionSheet.vue'
import FundEmptyState from '@/features/fund/FundEmptyState.vue'
import FundMemberList from '@/features/fund/FundMemberList.vue'
import FundSummaryCard from '@/features/fund/FundSummaryCard.vue'
import HolderSheet from '@/features/fund/HolderSheet.vue'
import { canTurnOff, readOnlyReason } from '@/features/fund/fundRules'
import { useContributionForm } from '@/features/fund/useContributionForm'
import { useFundHolder } from '@/features/fund/useFundHolder'
import { api } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

const props = defineProps<{
  trip: TripDetail
  fund: FundDetail | null
  today: string
  refresh: () => Promise<void>
}>()

const { t } = useI18n()
const tripId = () => props.trip.id
const reason = computed(() => readOnlyReason(props.trip))
const editable = computed(() => reason.value === null)

const contribution = useContributionForm(
  tripId,
  () => ({ memberId: props.trip.me, today: props.today }),
  props.refresh,
)
const holder = useFundHolder(tripId, props.refresh)
const removal = useConfirmedAction<Contribution>(async (item) => {
  const base = `/trips/${encodeURIComponent(props.trip.id)}/fund/contributions`
  await api.delete<void>(`${base}/${encodeURIComponent(item.id)}`)
  await props.refresh()
})
const changingHolder = ref(false)
const turningOff = ref(false)

const enableError = computed(() =>
  holder.error.value && !changingHolder.value && !turningOff.value
    ? t(errorMessageKey(holder.error.value))
    : null,
)
const linkClass =
  'inline-flex min-h-11 items-center text-sm font-medium underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky'

function openHolderSheet(): void {
  holder.error.value = null
  changingHolder.value = true
}

function openTurnOff(): void {
  holder.error.value = null
  turningOff.value = true
}

async function saveHolder(holderId: string): Promise<void> {
  if (await holder.setHolder(holderId)) changingHolder.value = false
}

async function turnOff(): Promise<void> {
  if (await holder.setHolder(null)) turningOff.value = false
}
</script>

<template>
  <div class="flex flex-1 flex-col gap-4">
    <p
      v-if="reason"
      class="card-ink bg-sand p-3 text-sm"
    >
      {{ t(reason) }}
    </p>
    <FundEmptyState
      v-if="!fund"
      :can-edit="editable"
      :pending="holder.pending.value"
      :error="enableError"
      @enable="holder.setHolder(trip.me)"
    />
    <template v-else>
      <FundSummaryCard
        :trip="trip"
        :fund="fund"
      />
      <FundMemberList
        :trip="trip"
        :fund="fund"
      />
      <ContributionList
        :trip="trip"
        :contributions="fund.contributions"
        :can-delete="editable"
        @delete="removal.ask"
      />
      <p class="text-muted text-sm">
        {{ t('fund.note') }}
      </p>
      <div
        v-if="editable"
        class="flex flex-wrap items-center justify-between gap-2"
      >
        <button
          type="button"
          :class="linkClass"
          @click="openHolderSheet"
        >
          {{ t('fund.changeHolder') }}
        </button>
        <button
          v-if="canTurnOff(fund)"
          type="button"
          :class="linkClass"
          @click="openTurnOff"
        >
          {{ t('fund.turnOff') }}
        </button>
      </div>
      <div
        v-if="editable"
        class="bg-cream sticky bottom-0 -mx-4 mt-auto px-4 pt-3 pb-[calc(1rem+env(safe-area-inset-bottom))]"
      >
        <BaseButton
          variant="success"
          block
          @click="contribution.show"
        >
          {{ t('fund.add') }}
        </BaseButton>
      </div>
    </template>

    <ContributionSheet
      v-model:member-id="contribution.form.memberId"
      v-model:amount="contribution.form.amount"
      v-model:date="contribution.form.date"
      :open="contribution.open.value"
      :trip="trip"
      :errors="contribution.errors.value"
      :submit-error="contribution.submitError.value"
      :pending="contribution.pending.value"
      @close="contribution.close"
      @submit="contribution.submit"
    />
    <HolderSheet
      :open="changingHolder"
      :trip="trip"
      :error="holder.error.value"
      :pending="holder.pending.value"
      @close="changingHolder = false"
      @save="saveHolder"
    />
    <ConfirmSheet
      :open="turningOff"
      :title="t('fund.turnOffTitle')"
      :message="t('fund.turnOffBody')"
      :confirm-label="t('fund.turnOffConfirm')"
      :pending="holder.pending.value"
      :error="holder.error.value ? t(errorMessageKey(holder.error.value)) : undefined"
      @confirm="turnOff"
      @cancel="turningOff = false"
    />
    <ConfirmSheet
      :open="removal.target.value !== null"
      danger
      :title="t('fund.deleteTitle')"
      :message="t('fund.deleteBody')"
      :confirm-label="t('fund.deleteConfirm')"
      :pending="removal.pending.value"
      :error="removal.error.value ? t(errorMessageKey(removal.error.value)) : undefined"
      @confirm="removal.confirm"
      @cancel="removal.cancel"
    />
  </div>
</template>
