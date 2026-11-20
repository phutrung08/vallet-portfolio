<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { CachedCopy } from '@/lib/api'
import { formatSavedAt } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

// Clock prop lets tests pin "now" deterministically.
const props = withDefaults(defineProps<{ copy: CachedCopy | null; now?: () => Date }>(), {
  now: () => new Date(),
})

const { t, locale } = useI18n()

function label(copy: CachedCopy): string {
  if (copy.savedAt === null) return t('offline.savedCopy')
  return t('offline.updatedAt', { time: formatSavedAt(copy.savedAt, props.now(), locale.value as AppLocale) })
}
</script>

<template>
  <p
    v-if="copy"
    class="text-muted text-xs"
  >
    {{ label(copy) }}
  </p>
</template>
