<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/BaseButton.vue'
import BottomSheet from '@/components/BottomSheet.vue'
import MemberPicker from '@/components/MemberPicker.vue'
import type { TripDetail } from '@/entities'
import { activeMembers } from '@/features/trips/tripMeta'
import { errorMessageKey } from '@/lib/errors'

const props = defineProps<{
  open: boolean
  trip: TripDetail
  error: unknown
  pending: boolean
}>()
const emit = defineEmits<{ close: []; save: [holderId: string] }>()

const { t } = useI18n()
const chosen = ref<string | null>(props.trip.fund_holder_id)
const options = computed(() =>
  activeMembers(props.trip).map((member) => ({ id: member.id, name: member.display_name })),
)

// Initialize picker to current fund holder whenever sheet opens.
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) chosen.value = props.trip.fund_holder_id
  },
)

function save(): void {
  if (chosen.value !== null) emit('save', chosen.value)
}
</script>

<template>
  <BottomSheet
    :open="open"
    :title="t('fund.holderSheet')"
    @close="emit('close')"
  >
    <div class="flex flex-col gap-4">
      <MemberPicker
        v-model="chosen"
        :label="t('fund.holderSheet')"
        :options="options"
      />
      <p
        v-if="error"
        role="alert"
        class="text-danger text-sm"
      >
        {{ t(errorMessageKey(error)) }}
      </p>
      <BaseButton
        variant="success"
        block
        :disabled="pending || chosen === null || chosen === trip.fund_holder_id"
        @click="save"
      >
        {{ t('fund.save') }}
      </BaseButton>
    </div>
  </BottomSheet>
</template>
