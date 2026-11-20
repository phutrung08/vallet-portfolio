<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Landmark } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import type { BankAccount } from '@/entities'

defineProps<{ account: BankAccount | null }>()
defineEmits<{ edit: [] }>()

const { t } = useI18n()
</script>

<template>
  <BaseButton
    variant="outline"
    block
    class="flex-wrap justify-between gap-x-2 rounded-card! py-1.5 text-left"
    @click="$emit('edit')"
  >
    <span class="flex items-center">
      <Landmark
        :size="18"
        class="mr-1.5 shrink-0"
        aria-hidden="true"
      />
      {{ t('balances.myAccount') }}
    </span>
    <span class="text-muted shrink-0 text-sm">
      {{
        account
          ? `${account.bank_short_name} ${t('balances.qr.last4', { last4: account.account_last4 })}`
          : t('balances.myAccountEmpty')
      }}
    </span>
  </BaseButton>
</template>
