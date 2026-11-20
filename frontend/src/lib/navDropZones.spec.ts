import { describe, expect, it } from 'vitest'
import { dropZones, nearestZone, type Rect } from '@/lib/navDropZones'

const phone = dropZones('phone', { width: 412, height: 915, rem: 16, dockLength: 292 })
const wide = dropZones('wide', { width: 1024, height: 768, rem: 16, dockLength: 744 })

const overlaps = (a: Rect, b: Rect) =>
  a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height

describe('dropZones', () => {
  it('offers five phone placements on large phones', () => {
    expect(phone.map((zone) => zone.id)).toEqual([
      'bottom-left',
      'bottom-center',
      'bottom-right',
      'edge-left',
      'edge-right',
    ])
  })

  it('offers two full-height rails on wide screens inside the 12px inset', () => {
    expect(wide.map((zone) => zone.id)).toEqual(['rail-left', 'rail-right'])
    expect(wide[0]?.rect).toEqual({ left: 12, top: 12, width: 64, height: 744 })
    expect(wide[1]?.rect).toEqual({ left: 948, top: 12, width: 64, height: 744 })
  })

  it.each([
    ['portrait', 412, 915],
    ['landscape', 560, 320],
  ])('never overlaps two phone drop zones (%s)', (_name, width, height) => {
    const zones = dropZones('phone', { width, height, rem: 16, dockLength: 292 })
    zones.forEach((a, i) => zones.slice(i + 1).forEach((b) => expect(overlaps(a.rect, b.rect)).toBe(false)))
    zones.forEach(({ rect }) => {
      expect(rect.left).toBeGreaterThanOrEqual(12)
      expect(rect.left + rect.width).toBeLessThanOrEqual(width - 12)
      expect(rect.top + rect.height).toBeLessThanOrEqual(height - 12)
    })
  })

  it('scales dimensions with root font size', () => {
    const [left] = dropZones('wide', { width: 1024, height: 768, rem: 20, dockLength: 0 })
    expect(left?.rect.width).toBe(80)
  })
})

describe('nearestZone', () => {
  it.each([
    [{ x: 20, y: 900 }, 'bottom-left'],
    [{ x: 206, y: 880 }, 'bottom-center'],
    [{ x: 400, y: 910 }, 'bottom-right'],
    [{ x: 0, y: 400 }, 'edge-left'],
    [{ x: 412, y: 300 }, 'edge-right'],
    [{ x: 200, y: 100 }, 'edge-left'],
    [{ x: 300, y: 600 }, 'edge-right'],
  ] as const)('picks %o on phone -> %s', (point, expected) => {
    expect(nearestZone(phone, point)).toBe(expected)
  })

  it.each([
    [{ x: 100, y: 400 }, 'rail-left'],
    [{ x: 500, y: 10 }, 'rail-left'],
    [{ x: 530, y: 700 }, 'rail-right'],
    [{ x: 1020, y: 760 }, 'rail-right'],
  ] as const)('picks %o on wide screen -> %s', (point, expected) => {
    expect(nearestZone(wide, point)).toBe(expected)
  })

  it('breaks ties by closer center distance', () => {
    const zones = [
      { id: 'edge-left', rect: { left: 0, top: 0, width: 100, height: 100 } },
      { id: 'edge-right', rect: { left: 50, top: 0, width: 100, height: 100 } },
    ] as const
    expect(nearestZone(zones, { x: 90, y: 50 })).toBe('edge-right')
    expect(nearestZone(zones, { x: 60, y: 50 })).toBe('edge-left')
  })

  it('returns null when zones list is empty', () => {
    expect(nearestZone([], { x: 0, y: 0 })).toBeNull()
  })
})
