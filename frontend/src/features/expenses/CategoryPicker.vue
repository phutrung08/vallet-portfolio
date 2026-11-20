<script setup lang="ts">
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ExpenseCategory } from '@/entities'
import { categoryIcons } from '@/features/expenses/categoryIcons'
import { CATEGORIES } from '@/features/expenses/expenseFormRules'

const model = defineModel<ExpenseCategory>({ required: true })

const { t } = useI18n()
const name = useId()
</script>

<template>
  <fieldset>
    <legend class="mb-1.5 text-sm font-medium">
      {{ t('expenseForm.category') }}
    </legend>
    <div class="flex flex-wrap gap-2">
      <label
        v-for="category in CATEGORIES"
        :key="category"
      >
        <input
          v-model="model"
          type="radio"
          :name="name"
          :value="category"
          class="peer sr-only"
        >
        <span
          class="ink-border rounded-pill bg-surface flex min-h-11 cursor-pointer items-center gap-1.5 px-3 text-sm font-medium peer-checked:bg-ink peer-checked:text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-sky"
        >
          <component
            :is="categoryIcons[category]"
            :size="16"
            aria-hidden="true"
          />
          {{ t(`expenseForm.categories.${category}`) }}
        </span>
      </label>
    </div>
  </fieldset>
</template>
