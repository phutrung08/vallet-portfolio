import type { Point } from '@/lib/navDropZones'

export function centerOf(element: Element): Point {
  const box = element.getBoundingClientRect()
  return { x: box.left + box.width / 2, y: box.top + box.height / 2 }
}

let disarmClickGuard: (() => void) | null = null

/**
 * Swallows the trailing click emitted onto a nav item when a drag completes.
 * Clears automatically on the next pointerdown so subsequent taps work; keyboard clicks (detail 0) pass.
 */
export function armClickGuard(): void {
  disarmClickGuard?.()
  const swallow = (event: MouseEvent) => {
    if (event.detail === 0) return
    event.preventDefault()
    event.stopPropagation()
    disarm()
  }
  const disarm = () => {
    window.removeEventListener('click', swallow, true)
    window.removeEventListener('pointerdown', disarm, true)
    disarmClickGuard = null
  }
  window.addEventListener('click', swallow, true)
  window.addEventListener('pointerdown', disarm, true)
  disarmClickGuard = disarm
}
