<script setup lang="ts">
import DeviceCard from '@/features/settings/DeviceCard.vue'
import NavPlacementCard from '@/features/settings/NavPlacementCard.vue'
import SettingsPreferences from '@/features/settings/SettingsPreferences.vue'
import SignOutCard from '@/features/settings/SignOutCard.vue'
import type { SettingsSectionKey } from '@/features/settings/settingsSections'

/** Renders the right-hand detail pane cards for the active settings category. */
defineProps<{ section: SettingsSectionKey }>()
</script>

<template>
  <template v-if="section === 'appearance'">
    <DeviceCard />
    <SettingsPreferences />
  </template>
  <NavPlacementCard v-else-if="section === 'nav'" />
  <SignOutCard v-else />
</template>
