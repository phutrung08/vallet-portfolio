<script setup lang="ts">
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'

const model = defineModel<boolean>({ required: true })

const { t } = useI18n()
const labelId = useId()
const helpId = useId()
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between gap-3">
      <div>
        <span
          :id="labelId"
          class="text-sm font-medium"
        >{{ t('createTrip.fund') }}</span>
        <p
          :id="helpId"
          class="text-muted text-xs"
        >
          {{ t('createTrip.fundHelp') }}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        :aria-checked="model"
        :aria-labelledby="labelId"
        :aria-describedby="helpId"
        class="flex min-h-11 min-w-11 shrink-0 items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
        @click="model = !model"
      >
        <span
          class="ink-border rounded-pill flex h-7 w-12 items-center p-0.5 transition-colors motion-reduce:transition-none"
          :class="model ? 'bg-green' : 'bg-sand'"
          aria-hidden="true"
        >
          <span
            class="ink-border bg-surface rounded-pill size-5 transition-transform motion-reduce:transition-none"
            :class="model && 'translate-x-5'"
          />
        </span>
      </button>
    </div>
    <p
      v-if="model"
      class="text-sm"
    >
      {{ t('createTrip.fundHolder') }}
    </p>
  </div>
</template>
