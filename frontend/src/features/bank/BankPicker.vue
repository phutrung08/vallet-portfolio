<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check } from 'lucide-vue-next'
import TextField from '@/components/TextField.vue'
import type { Bank } from '@/entities'
import { filterBanks } from '@/features/bank/accountRules'

/** Selected bank BIN. */
const model = defineModel<string | null>({ required: true })
const props = defineProps<{ banks: readonly Bank[]; error?: string }>()

const { t } = useI18n()
const query = ref('')
const shown = computed(() => filterBanks(props.banks, query.value))
</script>

<template>
  <div class="flex flex-col gap-2">
    <TextField
      v-model="query"
      :label="t('bank.search')"
      :error="error"
    />
    <ul
      role="group"
      :aria-label="t('bank.bankLabel')"
      class="ink-border rounded-card bg-surface max-h-48 overflow-y-auto"
    >
      <li
        v-if="shown.length === 0"
        class="text-muted p-3 text-sm"
      >
        {{ t('bank.noMatch') }}
      </li>
      <li
        v-for="bank in shown"
        :key="bank.bin"
      >
        <button
          type="button"
          :aria-pressed="bank.bin === model"
          class="flex min-h-11 w-full items-center gap-2 px-3 text-left focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-sky aria-pressed:bg-green-soft"
          @click="model = bank.bin"
        >
          <span class="min-w-0 flex-1 font-medium break-words">{{ bank.short_name }}</span>
          <span class="text-muted text-xs">{{ bank.code }}</span>
          <Check
            v-if="bank.bin === model"
            :size="18"
            class="shrink-0"
            aria-hidden="true"
          />
        </button>
      </li>
    </ul>
  </div>
</template>
