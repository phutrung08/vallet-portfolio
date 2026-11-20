<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import QrCode from '@/components/QrCode.vue'
import type { VietQr } from '@/entities'

defineProps<{ qr: VietQr }>()

const { t } = useI18n()
</script>

<template>
  <div class="flex flex-col items-center gap-3">
    <QrCode
      :value="qr.payload"
      :size="240"
      :label="t('balances.qr.label')"
      class="ink-border rounded-card max-w-full"
    />
    <dl class="flex w-full flex-col gap-0.5 text-center">
      <dt class="sr-only">
        {{ t('balances.qr.bank') }}
      </dt>
      <dd class="font-medium">
        {{ qr.bank_short_name }} · {{ t('balances.qr.last4', { last4: qr.account_last4 }) }}
      </dd>
      <dt class="sr-only">
        {{ t('balances.qr.holder') }}
      </dt>
      <dd class="font-medium break-words">
        {{ qr.account_name }}
      </dd>
      <dt class="sr-only">
        {{ t('balances.qr.message') }}
      </dt>
      <dd class="text-muted text-sm break-words">
        {{ qr.message }}
      </dd>
    </dl>
    <p class="text-muted text-center text-sm">
      {{ t('balances.qr.hint') }}
    </p>
  </div>
</template>
