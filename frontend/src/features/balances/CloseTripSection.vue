<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Lock, LockOpen } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import ConfirmSheet from '@/components/ConfirmSheet.vue'
import { api } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import { useConfirmedAction } from '@/lib/useConfirmedAction'

type Action = 'close' | 'reopen'

const props = defineProps<{ tripId: string; closed: boolean; refresh: () => Promise<void> }>()

const { t } = useI18n()
const action = useConfirmedAction<Action>(async (chosen) => {
  await api.post(`/trips/${encodeURIComponent(props.tripId)}/${chosen}`)
  await props.refresh()
})
// Keep the wording consistent while the confirmation dialog animates closed.
const shown = ref<Action>('close')
watch(action.target, (current) => {
  if (current) shown.value = current
})
const prefix = computed(() => `balances.${shown.value}`)
const next = computed<Action>(() => (props.closed ? 'reopen' : 'close'))
</script>

<template>
  <section>
    <BaseButton
      variant="outline"
      block
      @click="action.ask(next)"
    >
      <component
        :is="closed ? LockOpen : Lock"
        :size="18"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ t(`balances.${next}.label`) }}
    </BaseButton>
    <ConfirmSheet
      :open="action.target.value !== null"
      :title="t(`${prefix}.title`)"
      :message="t(`${prefix}.body`)"
      :confirm-label="t(`${prefix}.confirm`)"
      :pending="action.pending.value"
      :error="action.error.value ? t(errorMessageKey(action.error.value)) : undefined"
      @confirm="action.confirm"
      @cancel="action.cancel"
    />
  </section>
</template>
