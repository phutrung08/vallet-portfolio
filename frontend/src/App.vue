<script setup lang="ts">
import { useRegisterSW } from 'virtual:pwa-register/vue'
import { RouterView } from 'vue-router'
import OfflineBanner from '@/components/OfflineBanner.vue'
import UpdateToast from '@/components/UpdateToast.vue'

// registerType 'prompt': wait until the user explicitly chooses to reload into the updated worker.
const { needRefresh, updateServiceWorker } = useRegisterSW()
</script>

<template>
  <OfflineBanner />
  <RouterView />
  <UpdateToast
    :open="needRefresh"
    @reload="updateServiceWorker()"
    @close="needRefresh = false"
  />
</template>
