<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import SegmentedControl from '@/components/SegmentedControl.vue'
import { useLocaleChoice } from '@/features/settings/useLocaleChoice'
import { useThemeChoice } from '@/features/settings/useThemeChoice'
import { SUPPORTED_LOCALES } from '@/lib/i18n'
import { THEME_CHOICES } from '@/lib/theme'

const { t } = useI18n()
const { locale } = useLocaleChoice()
const { theme } = useThemeChoice()

const localeOptions = computed(() =>
  SUPPORTED_LOCALES.map((value) => ({ value, label: t(`settings.language.${value}`) })),
)
const themeOptions = computed(() =>
  THEME_CHOICES.map((value) => ({ value, label: t(`settings.theme.${value}`) })),
)
</script>

<template>
  <section class="flex flex-col gap-4">
    <div class="flex flex-col gap-1.5">
      <h2 class="text-base">
        {{ t('settings.language.label') }}
      </h2>
      <SegmentedControl
        v-model="locale"
        :label="t('settings.language.label')"
        :options="localeOptions"
      />
    </div>
    <div class="flex flex-col gap-1.5">
      <h2 class="text-base">
        {{ t('settings.theme.label') }}
      </h2>
      <SegmentedControl
        v-model="theme"
        :label="t('settings.theme.label')"
        :options="themeOptions"
      />
    </div>
  </section>
</template>
