<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import SplitLayout from '@/components/SplitLayout.vue'
import SettingsHeader from '@/features/settings/SettingsHeader.vue'
import SettingsSectionPane from '@/features/settings/SettingsSectionPane.vue'
import { SETTINGS_SECTIONS } from '@/features/settings/settingsSections'
import { useSectionSelection } from '@/features/settings/useSectionSelection'

const { t } = useI18n()
const version = import.meta.env.PACKAGE_VERSION
const { selected, select } = useSectionSelection()
</script>

<template>
  <SplitLayout :nav="false">
    <template #list>
      <SettingsHeader />
      <nav :aria-label="t('settings.sections.label')">
        <ul class="flex flex-col gap-2">
          <li
            v-for="section in SETTINGS_SECTIONS"
            :key="section.key"
            class="ink-border rounded-card"
            :class="selected === section.key ? 'bg-green-soft outline-green-ink outline-2 -outline-offset-2' : 'bg-surface'"
          >
            <button
              type="button"
              :aria-current="selected === section.key ? 'true' : undefined"
              class="flex min-h-12 w-full items-center gap-3 px-3 py-1.5 text-left font-medium focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sky"
              @click="select(section.key)"
            >
              <component
                :is="section.icon"
                :size="20"
                aria-hidden="true"
                class="shrink-0"
              />
              <span class="min-w-0 flex-1 break-words">{{ t(`settings.sections.${section.key}`) }}</span>
            </button>
          </li>
        </ul>
      </nav>
      <p class="mt-auto text-center text-xs text-muted">
        {{ t('settings.version', { version }) }}
      </p>
    </template>
    <template #detail>
      <SettingsSectionPane
        v-if="selected"
        :section="selected"
      />
    </template>
  </SplitLayout>
</template>
