import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { SETTINGS_SECTIONS, isSettingsSection, type SettingsSectionKey } from '@/features/settings/settingsSections'

/**
 * Tracks the active category in `?section=<key>` on split layouts.
 * Selecting a row pushes a history entry; unknown or missing values normalize with replace.
 */
export function useSectionSelection() {
  const route = useRoute()
  const router = useRouter()
  const selected = computed<SettingsSectionKey | null>(() =>
    isSettingsSection(route.query.section) ? route.query.section : null,
  )

  async function select(key: SettingsSectionKey): Promise<void> {
    if (key === selected.value) return
    await router.push({ query: { ...route.query, section: key } })
  }

  watch(
    selected,
    (key) => {
      if (!key) void router.replace({ query: { ...route.query, section: SETTINGS_SECTIONS[0].key } })
    },
    { immediate: true },
  )

  return { selected, select }
}
