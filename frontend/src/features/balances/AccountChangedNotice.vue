<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { TriangleAlert } from 'lucide-vue-next'
import BaseCard from '@/components/BaseCard.vue'
import { useMoment } from '@/lib/useMoment'

const props = defineProps<{ name: string; changedAt: string }>()

const { t } = useI18n()
const when = useMoment()(props.changedAt)
</script>

<template>
  <BaseCard
    tone="yellow"
    flat
    role="note"
    class="flex items-start gap-2"
  >
    <TriangleAlert
      :size="20"
      class="mt-0.5 shrink-0"
      aria-hidden="true"
    />
    <div class="min-w-0 text-sm">
      <p class="font-bold break-words">
        {{ t('balances.qr.accountChanged', { name, time: when.time, day: when.day }) }}
      </p>
      <p class="break-words">
        {{ t('balances.qr.accountChangedHint', { name }) }}
      </p>
    </div>
  </BaseCard>
</template>
