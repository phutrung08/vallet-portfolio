<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import BaseCard from '@/components/BaseCard.vue'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import { useSignOut } from '@/features/settings/useSignOut'
import { useTripList } from '@/features/trips/useTripList'
import { errorMessageKey } from '@/lib/errors'

const { t } = useI18n()
const { trips, status } = useTripList()
const signOut = useSignOut()

// Treat an unresolved or errored trip list the same as zero saved trips.
const tripCount = computed(() => (status.value === 'ready' ? trips.value.length : 0))
const message = computed(() =>
  tripCount.value > 0
    ? t('settings.signOut.confirm.body', tripCount.value)
    : t('settings.signOut.confirm.bodyNoCount'),
)
</script>

<template>
  <BaseCard
    as="section"
    class="flex flex-col gap-3 p-4"
  >
    <h2 class="text-xl">
      {{ t('settings.signOut.title') }}
    </h2>
    <p class="text-muted text-sm">
      {{ t('settings.signOut.body') }}
    </p>
    <BaseButton
      variant="danger-outline"
      block
      :disabled="signOut.pending.value"
      @click="signOut.ask(true)"
    >
      {{ t('settings.signOut.button') }}
    </BaseButton>
    <ConfirmSheet
      :open="signOut.target.value !== null"
      danger
      :title="t('settings.signOut.confirm.title')"
      :message="message"
      :confirm-label="t('settings.signOut.confirm.confirm')"
      :cancel-label="t('settings.signOut.confirm.stay')"
      :pending="signOut.pending.value"
      :error="signOut.error.value ? t(errorMessageKey(signOut.error.value)) : undefined"
      @confirm="signOut.confirm"
      @cancel="signOut.cancel"
    />
  </BaseCard>
</template>
