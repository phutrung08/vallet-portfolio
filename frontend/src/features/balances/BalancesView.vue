<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import BasePill from '@/components/BasePill.vue'
import BottomNav from '@/components/BottomNav.vue'
import CachedNotice from '@/components/CachedNotice.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import PullIndicator from '@/components/PullIndicator.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SplitLayout from '@/components/SplitLayout.vue'
import BalancesContent from '@/features/balances/BalancesContent.vue'
import BalancesDetailPane from '@/features/balances/BalancesDetailPane.vue'
import { useBalancesPage } from '@/features/balances/useBalancesPage'
import { transferKey, useTransferSelection } from '@/features/balances/useTransferSelection'
import BankAccountSheet from '@/features/bank/BankAccountSheet.vue'
import { useAddExpense } from '@/features/expenses/useAddExpense'
import { ApiError } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useDesktopBarTrip } from '@/lib/desktopBarContext'
import { useTripSource } from '@/lib/tripSource'
import { useNavLabels, useNavShortLabels } from '@/lib/useNavLabels'
import { usePullToRefresh } from '@/lib/usePullToRefresh'
import { useSplit } from '@/lib/useSplit'

const { t } = useI18n()
const route = useRoute()
const tripId = computed(() => String(route.params.tripId))
const { trip, balances, payments, accounts, status, error, cachedCopy, reload, refresh } =
  useBalancesPage(() => tripId.value, useTripSource().read)
const layout = useTemplateRef('layout')
const pull = usePullToRefresh(computed(() => layout.value?.listPane ?? null), refresh)
watch(tripId, reload)
const navLabels = useNavLabels()
const navShortLabels = useNavShortLabels()

const addExpense = useAddExpense(() => tripId.value)

// Settlement payments are fine on a closed trip; only a locked trip (or demo mode) is read-only.
const { readonly } = useTripSource()
useDesktopBarTrip(() => trip.value, readonly)
const editable = computed(() => trip.value !== undefined && !trip.value.locked && !readonly)
// From the `split` breakpoint the open transfer renders in the right detail pane.
const split = useSplit()
const selection = useTransferSelection(
  computed(() => split.value && editable.value),
  () => balances.value?.transfers ?? [],
  () => trip.value?.me ?? '',
)
const editingAccount = ref(false)
const myAccount = computed(() => accounts.value.find((item) => item.member_id === trip.value?.me) ?? null)
</script>

<template>
  <SplitLayout ref="layout">
    <template #list>
      <PullIndicator
        :offset="pull.offset.value"
        :armed="pull.armed.value"
        :refreshing="pull.refreshing.value"
      />
      <header class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h1 class="text-2xl">
          {{ t('balances.title') }}
        </h1>
        <BasePill
          v-if="trip"
          tone="sky"
          class="min-w-0 truncate"
        >
          {{ trip.name }}
        </BasePill>
        <BasePill
          v-if="trip?.closed"
          tone="yellow"
        >
          {{ t('trips.status.closed') }}
        </BasePill>
        <RefreshButton
          class="-mr-2 ml-auto"
          :refreshing="pull.refreshing.value"
          @refresh="pull.refresh"
        />
      </header>

      <div
        v-if="status === 'loading'"
        aria-busy="true"
      >
        <span class="sr-only">{{ t('common.loading') }}</span>
        <div class="card-ink bg-sand h-36 animate-pulse motion-reduce:animate-none" />
      </div>
      <ErrorNotice
        v-else-if="status === 'error'"
        :message="t(errorMessageKey(error))"
        :can-retry="!(error instanceof ApiError && error.code === 'not_found')"
        @retry="reload"
      />
      <template v-else-if="trip && balances">
        <CachedNotice :copy="cachedCopy" />
        <BalancesContent
          :trip="trip"
          :balances="balances"
          :payments="payments"
          :accounts="accounts"
          :editable="editable"
          :split="split"
          :selected-key="selection.selected.value ? transferKey(selection.selected.value) : null"
          :refresh="refresh"
          @select="selection.select"
          @edit-account="editingAccount = true"
        />
      </template>
    </template>
    <template #detail>
      <BalancesDetailPane
        v-if="split && trip && balances"
        :trip="trip"
        :transfers="balances.transfers"
        :selected="selection.selected.value"
        :accounts="accounts"
        :editable="editable"
        :on-recorded="refresh"
        @add-account="editingAccount = true"
      />
    </template>
  </SplitLayout>
  <BankAccountSheet
    v-if="trip"
    :open="editingAccount"
    :trip-id="trip.id"
    :current="myAccount"
    :changed="refresh"
    @close="editingAccount = false"
  />
  <BottomNav
    v-if="trip"
    :trip-id="trip.id"
    :labels="navLabels"
    :short-labels="navShortLabels"
    :can-add="!trip.closed && !trip.locked"
    @add="addExpense"
  />
</template>
