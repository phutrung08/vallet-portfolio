import { reactive, readonly } from 'vue'

export const NAV_STORAGE_KEY = 'vallet.nav'
export const PHONE_PLACEMENTS = [
  'bottom-left',
  'bottom-center',
  'bottom-right',
  'edge-left',
  'edge-right',
] as const
export const WIDE_PLACEMENTS = ['rail-left', 'rail-right'] as const
export type PhonePlacement = (typeof PHONE_PLACEMENTS)[number]
export type WidePlacement = (typeof WIDE_PLACEMENTS)[number]
export interface NavPlacement {
  phone: PhonePlacement
  wide: WidePlacement
}
export const DEFAULT_NAV_PLACEMENT: NavPlacement = { phone: 'bottom-center', wide: 'rail-left' }

const state = reactive<NavPlacement>({ ...DEFAULT_NAV_PLACEMENT })

function pick<T extends string>(choices: readonly T[], value: unknown, fallback: T): T {
  return choices.find((choice) => choice === value) ?? fallback
}

function readStored(): NavPlacement {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(NAV_STORAGE_KEY) ?? 'null')
    const record = typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {}
    return {
      phone: pick(PHONE_PLACEMENTS, record.phone, DEFAULT_NAV_PLACEMENT.phone),
      wide: pick(WIDE_PLACEMENTS, record.wide, DEFAULT_NAV_PLACEMENT.wide),
    }
  } catch {
    return { ...DEFAULT_NAV_PLACEMENT }
  }
}

/** Shared CSS keys the content and toast reserves read off these root attributes. */
function applyToRoot(): void {
  document.documentElement.dataset.navPhone = state.phone
  document.documentElement.dataset.navWide = state.wide
}

function persist(): void {
  try {
    localStorage.setItem(NAV_STORAGE_KEY, JSON.stringify({ phone: state.phone, wide: state.wide }))
  } catch {
    // Storage can be unavailable (private mode); the preference is simply kept in memory.
  }
}

/** Loads the device preference and applies it; call once at startup. */
export function initNavPlacement(): void {
  Object.assign(state, readStored())
  applyToRoot()
}

const placement = readonly(state)

function setPhone(next: PhonePlacement): void {
  state.phone = next
  applyToRoot()
  persist()
}

function setWide(next: WidePlacement): void {
  state.wide = next
  applyToRoot()
  persist()
}

export function useNavPlacement() {
  return { placement, setPhone, setWide }
}
