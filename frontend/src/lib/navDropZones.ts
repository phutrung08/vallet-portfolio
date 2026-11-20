import type { PhonePlacement, WidePlacement } from '@/lib/useNavPlacement'

/** Where the nav can be dragged: a large phone (dock or edge dock) or a wide screen (rail). */
export type WindowClass = 'phone' | 'wide'
export type ZoneId = PhonePlacement | WidePlacement

export interface Point {
  x: number
  y: number
}

export interface Rect {
  left: number
  top: number
  width: number
  height: number
}

export interface DropZone {
  id: ZoneId
  rect: Rect
}

/** Layout dimensions in px: the viewport size, root font size, and dock's long side. */
export interface ZoneFrame {
  width: number
  height: number
  rem: number
  dockLength: number
}

// Mirrors styles/nav.css: 0.75rem from screen edge, 4rem side dock or rail, 3.75rem dock height.
const INSET_REM = 0.75
const SIDE_REM = 4
const DOCK_REM = 3.75
const GAP_REM = 0.5

/**
 * Bottom targets split the bottom strip into thirds so their outlines never overlap; edge targets
 * sit centered in the vertical space above that strip.
 */
function phoneZones({ width, height, rem, dockLength }: ZoneFrame): DropZone[] {
  const inset = INSET_REM * rem
  const gap = GAP_REM * rem
  const side = SIDE_REM * rem
  const dock = DOCK_REM * rem
  const third = (width - 2 * inset - 2 * gap) / 3
  const bottomTop = height - inset - dock
  const room = bottomTop - gap - inset
  const edgeHeight = Math.min(dockLength, room)
  const edgeTop = inset + (room - edgeHeight) / 2
  const bottom = (index: number): Rect => ({
    left: inset + index * (third + gap),
    top: bottomTop,
    width: third,
    height: dock,
  })
  return [
    { id: 'bottom-left', rect: bottom(0) },
    { id: 'bottom-center', rect: bottom(1) },
    { id: 'bottom-right', rect: bottom(2) },
    { id: 'edge-left', rect: { left: inset, top: edgeTop, width: side, height: edgeHeight } },
    { id: 'edge-right', rect: { left: width - inset - side, top: edgeTop, width: side, height: edgeHeight } },
  ]
}

function wideZones({ width, height, rem }: ZoneFrame): DropZone[] {
  const inset = INSET_REM * rem
  const side = SIDE_REM * rem
  const rail = (left: number): Rect => ({ left, top: inset, width: side, height: height - 2 * inset })
  return [
    { id: 'rail-left', rect: rail(inset) },
    { id: 'rail-right', rect: rail(width - inset - side) },
  ]
}

/** Valid drop targets for the current window class in viewport coordinates. */
export function dropZones(kind: WindowClass, frame: ZoneFrame): DropZone[] {
  return kind === 'phone' ? phoneZones(frame) : wideZones(frame)
}

function distanceToRect(point: Point, rect: Rect): number {
  const dx = Math.max(rect.left - point.x, 0, point.x - (rect.left + rect.width))
  const dy = Math.max(rect.top - point.y, 0, point.y - (rect.top + rect.height))
  return Math.hypot(dx, dy)
}

function distanceToCenter(point: Point, rect: Rect): number {
  return Math.hypot(point.x - (rect.left + rect.width / 2), point.y - (rect.top + rect.height / 2))
}

/** Nearest zone to the pointer (distance 0 inside); ties break by center distance. */
export function nearestZone(zones: readonly DropZone[], point: Point): ZoneId | null {
  let best: DropZone | null = null
  for (const zone of zones) {
    if (!best) {
      best = zone
      continue
    }
    const delta = distanceToRect(point, zone.rect) - distanceToRect(point, best.rect)
    if (delta < 0 || (delta === 0 && distanceToCenter(point, zone.rect) < distanceToCenter(point, best.rect))) {
      best = zone
    }
  }
  return best?.id ?? null
}
