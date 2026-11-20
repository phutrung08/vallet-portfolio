import { nextTick, onScopeDispose, ref, shallowRef, watch, type Ref } from 'vue'
import { useMediaQuery } from '@/lib/useMediaQuery'
import { PHONE_PLACEMENTS, useNavPlacement, type PhonePlacement } from '@/lib/useNavPlacement'
import { dropZones, nearestZone, type DropZone, type Point, type ZoneId } from '@/lib/navDropZones'
import { armClickGuard, centerOf } from '@/lib/navDragDom'

/** How long a stationary press must last before the nav lifts. */
export const HOLD_MS = 400
/** Travel (px) that treats a press as scroll before the hold, or as movement after it. */
export const SLOP_PX = 8
/** Snap duration matching the `settling` transition in styles/nav.css. */
export const SNAP_MS = 180

export type DragPhase = 'idle' | 'pressing' | 'dragging' | 'settling'

const isPhonePlacement = (id: ZoneId): id is PhonePlacement =>
  (PHONE_PLACEMENTS as readonly string[]).includes(id)

/**
 * Press and hold the navigation bar, then drag it to another dock or rail slot.
 * Enabled from --breakpoint-phone-lg (25rem) upward; short taps and early scroll moves pass through.
 */
export function useNavDrag(nav: Readonly<Ref<HTMLElement | null>>) {
  const enabled = useMediaQuery('(min-width: 25rem)')
  const isWide = useMediaQuery('(min-width: 37.5rem)')
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
  const { placement, setPhone, setWide } = useNavPlacement()

  const phase = ref<DragPhase>('idle')
  const zones = shallowRef<DropZone[]>([])
  const target = ref<ZoneId | null>(null)
  /** Destination of the latest drop, announced by NavDragLayer's live region. */
  const moved = ref<ZoneId | null>(null)
  let origin: Point = { x: 0, y: 0 }
  let pointerId = -1
  let travelled = false
  let timer: ReturnType<typeof setTimeout> | undefined

  const current = (): ZoneId => (isWide.value ? placement.wide : placement.phone)

  function setPhase(next: DragPhase): void {
    phase.value = next
    const element = nav.value
    if (!element) return
    if (next === 'dragging' || next === 'settling') element.dataset.drag = next
    else delete element.dataset.drag
  }

  function finish(): void {
    clearTimeout(timer)
    window.removeEventListener('keydown', onKeydown)
    nav.value?.style.removeProperty('translate')
    zones.value = []
    target.value = null
    setPhase('idle')
  }

  /** Animates back to the resting position unless reduced motion is preferred. */
  function settle(): void {
    if (reducedMotion.value) {
      finish()
      return
    }
    setPhase('settling')
    nav.value?.style.removeProperty('translate')
    clearTimeout(timer)
    timer = setTimeout(finish, SNAP_MS)
  }

  function lift(): void {
    const element = nav.value
    if (!element) {
      finish()
      return
    }
    const box = element.getBoundingClientRect()
    zones.value = dropZones(isWide.value ? 'wide' : 'phone', {
      width: document.documentElement.clientWidth,
      height: document.documentElement.clientHeight,
      rem: parseFloat(getComputedStyle(document.documentElement).fontSize) || 16,
      dockLength: Math.max(box.width, box.height),
    })
    target.value = current()
    setPhase('dragging')
    navigator.vibrate?.(10)
  }

  /** Applies the chosen placement and FLIP-animates `translate` from the release position. */
  async function drop(next: ZoneId): Promise<void> {
    const element = nav.value
    if (!element) {
      finish()
      return
    }
    const before = centerOf(element)
    if (isPhonePlacement(next)) setPhone(next)
    else setWide(next)
    moved.value = next
    await nextTick()
    element.style.removeProperty('translate')
    if (reducedMotion.value) {
      finish()
      return
    }
    const after = centerOf(element)
    element.style.setProperty('translate', `${before.x - after.x}px ${before.y - after.y}px`)
    // Forces layout commit so the `settling` transition starts from the release offset.
    element.getBoundingClientRect()
    settle()
  }

  function onPointerDown(event: PointerEvent): void {
    if (phase.value !== 'idle' || !event.isPrimary || event.button !== 0) return
    origin = { x: event.clientX, y: event.clientY }
    pointerId = event.pointerId
    travelled = false
    setPhase('pressing')
    window.addEventListener('keydown', onKeydown)
    timer = setTimeout(lift, HOLD_MS)
  }

  function onPointerMove(event: PointerEvent): void {
    if (event.pointerId !== pointerId) return
    const dx = event.clientX - origin.x
    const dy = event.clientY - origin.y
    const far = Math.hypot(dx, dy) > SLOP_PX
    if (phase.value === 'pressing' && far) {
      finish()
      return
    }
    if (phase.value !== 'dragging') return
    if (far && !travelled) {
      travelled = true
      // Captured only once movement exceeds slop so long presses without dragging still activate items.
      nav.value?.setPointerCapture(pointerId)
    }
    nav.value?.style.setProperty('translate', `${dx}px ${dy}px`)
    target.value = nearestZone(zones.value, { x: event.clientX, y: event.clientY })
  }

  function onPointerUp(event: PointerEvent): void {
    if (event.pointerId !== pointerId) return
    if (phase.value === 'pressing') {
      finish()
      return
    }
    if (phase.value !== 'dragging') return
    const next = target.value
    if (!travelled) {
      settle()
      return
    }
    armClickGuard()
    if (next && next !== current()) void drop(next)
    else settle()
  }

  function onPointerCancel(event: PointerEvent): void {
    if (event.pointerId !== pointerId) return
    if (phase.value === 'pressing') finish()
    else if (phase.value === 'dragging') settle()
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape') return
    if (phase.value === 'pressing') finish()
    else if (phase.value === 'dragging') {
      armClickGuard()
      settle()
    }
  }

  /** Blocks native link drag or page scroll while the nav is lifted. */
  function blockWhileHeld(event: Event): void {
    if (phase.value === 'dragging') event.preventDefault()
  }

  /** Suppresses the touch context menu while holding or dragging the nav. */
  function blockMenu(event: Event): void {
    if (phase.value === 'pressing' || phase.value === 'dragging') event.preventDefault()
  }

  const listeners = {
    pointerdown: onPointerDown,
    pointermove: onPointerMove,
    pointerup: onPointerUp,
    pointercancel: onPointerCancel,
    contextmenu: blockMenu,
    dragstart: blockWhileHeld,
    // touch-action cannot flip mid-gesture, so cancelling touchmove keeps scrolling frozen.
    touchmove: blockWhileHeld,
  } as const

  watch(
    [nav, enabled],
    ([element, on], _previous, onCleanup) => {
      if (!element || !on) return
      for (const [type, handler] of Object.entries(listeners)) {
        element.addEventListener(type, handler as EventListener, { passive: false })
      }
      onCleanup(() => {
        for (const [type, handler] of Object.entries(listeners)) {
          element.removeEventListener(type, handler as EventListener)
        }
        finish()
      })
    },
    { immediate: true },
  )
  onScopeDispose(finish)

  return { enabled, phase, zones, target, moved }
}
