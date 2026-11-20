import { Palette, PanelLeft, UserRound } from 'lucide-vue-next'

/** Categories of the two-pane settings screen in display order; the first opens by default. */
export const SETTINGS_SECTIONS = [
  { key: 'appearance', icon: Palette },
  { key: 'nav', icon: PanelLeft },
  { key: 'account', icon: UserRound },
] as const

export type SettingsSectionKey = (typeof SETTINGS_SECTIONS)[number]['key']

export function isSettingsSection(value: unknown): value is SettingsSectionKey {
  return SETTINGS_SECTIONS.some((section) => section.key === value)
}
