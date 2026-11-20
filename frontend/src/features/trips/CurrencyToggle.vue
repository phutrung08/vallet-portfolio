<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { CurrencyCode } from '@/lib/format'

const model = defineModel<CurrencyCode>({ required: true })

const { t } = useI18n()
const options: CurrencyCode[] = ['VND', 'USD']
</script>

<template>
  <fieldset class="flex flex-col gap-1.5">
    <legend class="mb-1.5 text-sm font-medium">
      {{ t('createTrip.currency') }}
    </legend>
    <div class="flex gap-2">
      <label
        v-for="code in options"
        :key="code"
        class="flex-1"
      >
        <input
          v-model="model"
          type="radio"
          name="currency"
          :value="code"
          class="peer sr-only"
        >
        <span
          class="ink-border rounded-pill bg-surface flex min-h-11 cursor-pointer items-center justify-center font-medium peer-checked:bg-ink peer-checked:text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-sky"
        >{{ code }}</span>
      </label>
    </div>
  </fieldset>
</template>
