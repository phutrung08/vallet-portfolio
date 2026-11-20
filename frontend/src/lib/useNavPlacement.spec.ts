import { afterEach, describe, expect, it, vi } from 'vitest'
import { NAV_STORAGE_KEY, initNavPlacement, useNavPlacement } from '@/lib/useNavPlacement'

const root = document.documentElement

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  initNavPlacement()
})

describe('useNavPlacement', () => {
  it('defaults to a bottom-center dock and a left rail', () => {
    initNavPlacement()
    const { placement } = useNavPlacement()
    expect(placement).toEqual({ phone: 'bottom-center', wide: 'rail-left' })
    expect(root.dataset.navPhone).toBe('bottom-center')
    expect(root.dataset.navWide).toBe('rail-left')
  })

  it('persists each choice and mirrors it on the root element', () => {
    const { placement, setPhone, setWide } = useNavPlacement()
    setPhone('edge-left')
    setWide('rail-right')
    expect(placement).toEqual({ phone: 'edge-left', wide: 'rail-right' })
    expect(JSON.parse(localStorage.getItem(NAV_STORAGE_KEY) ?? '')).toEqual({
      phone: 'edge-left',
      wide: 'rail-right',
    })
    expect(root.dataset.navPhone).toBe('edge-left')
    expect(root.dataset.navWide).toBe('rail-right')
  })

  it('restores a stored choice on init', () => {
    localStorage.setItem(NAV_STORAGE_KEY, JSON.stringify({ phone: 'bottom-right', wide: 'rail-right' }))
    initNavPlacement()
    expect(useNavPlacement().placement).toEqual({ phone: 'bottom-right', wide: 'rail-right' })
  })

  it.each(['not json', '42', 'null', '{"phone":"top","wide":3}', '[]'])(
    'falls back to defaults for malformed storage %s',
    (stored) => {
      localStorage.setItem(NAV_STORAGE_KEY, stored)
      initNavPlacement()
      expect(useNavPlacement().placement).toEqual({ phone: 'bottom-center', wide: 'rail-left' })
    },
  )

  it('keeps the valid half when only one field is invalid', () => {
    localStorage.setItem(NAV_STORAGE_KEY, JSON.stringify({ phone: 'edge-right', wide: 'rail-top' }))
    initNavPlacement()
    expect(useNavPlacement().placement).toEqual({ phone: 'edge-right', wide: 'rail-left' })
  })

  it('works when localStorage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    initNavPlacement()
    const { placement, setPhone } = useNavPlacement()
    expect(placement.phone).toBe('bottom-center')
    setPhone('edge-left')
    expect(placement.phone).toBe('edge-left')
    expect(root.dataset.navPhone).toBe('edge-left')
  })
})
