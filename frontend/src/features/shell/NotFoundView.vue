<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

const { t } = useI18n()
</script>

<template>
  <main class="col-center p-4">
    <div class="card-ink bg-surface p-4">
      <h1>{{ t('notFound.title') }}</h1>
      <RouterLink
        to="/"
        class="mt-3 inline-flex min-h-11 items-center font-medium text-ink underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
      >
        {{ t('notFound.home') }}
      </RouterLink>
    </div>
  </main>
</template>
