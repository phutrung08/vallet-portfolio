import { onScopeDispose, readonly, shallowRef, watch } from 'vue'
import type { TripDetail } from '@/entities'

/** Compact trip summary surfaced inside DesktopTopBar above the desktop breakpoint. */
export interface DesktopBarTrip {
  id: string
  name: string
  memberCount: number
  closed: boolean
  locked: boolean
  readonly: boolean
}

const activeTrip = shallowRef<DesktopBarTrip | null>(null)
let activeOwner: symbol | null = null

/**
 * Registers the active view's trip for DesktopTopBar while the caller's effect scope is alive.
 * Disposing an older view never clears state already claimed by a newer view during route transitions.
 */
export function useDesktopBarTrip(trip: () => TripDetail | undefined, isReadonly = false): void {
  const token = Symbol('desktop-bar-owner')
  activeOwner = token

  watch(
    trip,
    (value) => {
      if (activeOwner !== token) return
      if (!value) {
        activeTrip.value = null
        return
      }
      activeTrip.value = {
        id: value.id,
        name: value.name,
        memberCount: value.members.filter((member) => !member.removed).length,
        closed: value.closed,
        locked: value.locked,
        readonly: isReadonly,
      }
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    if (activeOwner === token) {
      activeTrip.value = null
      activeOwner = null
    }
  })
}

/** Reactive read-only view of the currently registered desktop top-bar trip. */
export function useDesktopBarContext() {
  return readonly(activeTrip)
}

/** Clears registered desktop top-bar state (intended for unit tests). */
export function resetDesktopBarContext(): void {
  activeTrip.value = null
  activeOwner = null
}
