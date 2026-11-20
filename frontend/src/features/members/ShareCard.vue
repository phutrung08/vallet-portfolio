<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, QrCode as QrIcon, Share2 } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import BaseCard from '@/components/BaseCard.vue'
import BottomSheet from '@/components/BottomSheet.vue'
import QrCode from '@/components/QrCode.vue'

defineProps<{
  link: string
  copyState: 'idle' | 'copied' | 'failed'
  canShare: boolean
}>()
defineEmits<{ copy: []; share: [] }>()

const { t } = useI18n()
const showingQr = ref(false)
</script>

<template>
  <BaseCard
    tone="sky"
    class="flex flex-col gap-3 p-4"
  >
    <h2 class="text-lg">
      {{ t('members.invite.title') }}
    </h2>
    <p class="text-sm">
      {{ t('members.invite.body') }}
    </p>
    <p class="text-xs break-all">
      {{ link }}
    </p>
    <div class="flex flex-wrap gap-2">
      <BaseButton
        variant="dark"
        @click="$emit('copy')"
      >
        <Copy
          :size="16"
          class="mr-1.5"
          aria-hidden="true"
        />
        {{ copyState === 'copied' ? t('members.invite.copied') : t('members.invite.copy') }}
      </BaseButton>
      <BaseButton
        v-if="canShare"
        variant="outline"
        @click="$emit('share')"
      >
        <Share2
          :size="16"
          class="mr-1.5"
          aria-hidden="true"
        />
        {{ t('members.invite.share') }}
      </BaseButton>
      <BaseButton
        variant="outline"
        @click="showingQr = true"
      >
        <QrIcon
          :size="16"
          class="mr-1.5"
          aria-hidden="true"
        />
        {{ t('members.invite.qr') }}
      </BaseButton>
    </div>
    <p
      v-if="copyState === 'failed'"
      role="alert"
      class="text-danger text-sm"
    >
      {{ t('members.invite.copyFailed') }}
    </p>
    <BottomSheet
      :open="showingQr"
      :title="t('members.invite.qrTitle')"
      @close="showingQr = false"
    >
      <div class="flex justify-center pb-2">
        <QrCode
          :value="link"
          :label="t('members.invite.qrLabel')"
          class="ink-border rounded-card max-w-full"
        />
      </div>
    </BottomSheet>
  </BaseCard>
</template>
