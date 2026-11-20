<script setup lang="ts">
import SettingsSplit from '@/features/settings/SettingsSplit.vue'
import SettingsStack from '@/features/settings/SettingsStack.vue'
import { useSplit } from '@/lib/useSplit'

// At or above the `split` breakpoint, categories sit beside their detail cards; phones stack vertically.
const split = useSplit()
</script>

<template>
  <SettingsSplit v-if="split" />
  <SettingsStack v-else />
</template>
