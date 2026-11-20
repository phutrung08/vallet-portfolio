<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DeviceCard from '@/features/settings/DeviceCard.vue'
import NavPlacementCard from '@/features/settings/NavPlacementCard.vue'
import SettingsHeader from '@/features/settings/SettingsHeader.vue'
import SettingsPreferences from '@/features/settings/SettingsPreferences.vue'
import SignOutCard from '@/features/settings/SignOutCard.vue'

const { t } = useI18n()
const version = import.meta.env.PACKAGE_VERSION
</script>

<template>
  <main class="col-center flex min-h-dvh flex-col gap-4 p-4">
    <SettingsHeader />

    <DeviceCard />
    <SettingsPreferences />
    <NavPlacementCard />
    <SignOutCard />

    <p class="mt-auto text-center text-xs text-muted">
      {{ t('settings.version', { version }) }}
    </p>
  </main>
</template>
