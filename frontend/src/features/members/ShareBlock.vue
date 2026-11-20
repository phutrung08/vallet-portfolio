<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ErrorNotice from '@/components/ErrorNotice.vue'
import ShareCard from '@/features/members/ShareCard.vue'
import type { useShareLink } from '@/features/members/useShareLink'
import { errorMessageKey } from '@/lib/errors'

/** Renders the trip invite card once loaded, or a retryable error banner if loading fails. */
defineProps<{ share: ReturnType<typeof useShareLink> }>()

const { t } = useI18n()
</script>

<template>
  <ShareCard
    v-if="share.link.value"
    :link="share.link.value"
    :copy-state="share.copyState.value"
    :can-share="share.canShare"
    @copy="share.copy"
    @share="share.share"
  />
  <ErrorNotice
    v-else-if="share.status.value === 'error'"
    :message="t(errorMessageKey(share.error.value))"
    @retry="share.reload"
  />
</template>
