<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { KeyRound, Lock, LockOpen, LogOut } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import { useTripSecurity, type SecurityAction } from '@/features/members/useTripSecurity'
import { errorMessageKey } from '@/lib/errors'

const props = defineProps<{
  tripId: string
  locked: boolean
  rotate: () => Promise<void>
  refresh: () => Promise<void>
}>()

const { t } = useI18n()
const security = useTripSecurity(() => props.tripId, props.rotate, props.refresh)
const action = computed(() => security.target.value)
// Preserve sheet copy while the confirm dialog closes.
const shown = ref<SecurityAction>('rotate')
watch(action, (current) => {
  if (current) shown.value = current
})
const prefix = computed(() => `members.security.${shown.value}`)
</script>

<template>
  <section class="flex flex-col gap-2">
    <h2 class="text-lg">
      {{ t('members.security.title') }}
    </h2>
    <BaseButton
      variant="outline"
      block
      @click="security.ask('rotate')"
    >
      <KeyRound
        :size="18"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ t('members.security.rotate.label') }}
    </BaseButton>
    <BaseButton
      variant="outline"
      block
      @click="security.ask(locked ? 'unlock' : 'lock')"
    >
      <component
        :is="locked ? LockOpen : Lock"
        :size="18"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ t(locked ? 'members.security.unlock.label' : 'members.security.lock.label') }}
    </BaseButton>
    <BaseButton
      variant="danger-outline"
      block
      @click="security.ask('leave')"
    >
      <LogOut
        :size="18"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ t('members.security.leave.label') }}
    </BaseButton>
    <ConfirmSheet
      :open="action !== null"
      :danger="action === 'leave'"
      :title="t(`${prefix}.title`)"
      :message="t(`${prefix}.body`)"
      :confirm-label="t(`${prefix}.confirm`)"
      :pending="security.pending.value"
      :error="security.error.value ? t(errorMessageKey(security.error.value)) : undefined"
      @confirm="security.confirm"
      @cancel="security.cancel"
    />
  </section>
</template>
