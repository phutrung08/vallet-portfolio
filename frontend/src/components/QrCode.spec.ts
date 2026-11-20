import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import QrCode from '@/components/QrCode.vue'

const VALUE = 'https://vallet.example/join#abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG'
// Background rect + 706 dark modules (37x37 level-M code).
const RECT_COUNT = 707

describe('QrCode', () => {
  it('draws a square matrix with a quiet zone, one rect per dark module', () => {
    const svg = mount(QrCode, { props: { value: VALUE } }).get('svg')
    const [, , width, height] = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    expect(width).toBe(height)
    expect(((width ?? 0) - 8 - 17) % 4).toBe(0)
    expect(svg.findAll('rect')).toHaveLength(RECT_COUNT)
  })

  it('is deterministic and changes with the value', () => {
    const count = (value: string) => mount(QrCode, { props: { value } }).findAll('rect').length
    expect(count(VALUE)).toBe(count(VALUE))
    expect(count('https://vallet.example/join#other-token')).not.toBe(count(VALUE))
  })

  it('sizes the svg and exposes a label only when given', () => {
    const plain = mount(QrCode, { props: { value: VALUE, size: 120 } }).get('svg')
    expect(plain.attributes('width')).toBe('120')
    expect(plain.attributes('aria-hidden')).toBe('true')
    const labelled = mount(QrCode, { props: { value: VALUE, label: 'QR' } }).get('svg')
    expect(labelled.attributes('aria-label')).toBe('QR')
    expect(labelled.attributes('aria-hidden')).toBeUndefined()
  })

  it('keeps a white background and fixed dark modules whatever the theme', () => {
    document.documentElement.setAttribute('data-theme', 'dark')
    const rects = mount(QrCode, { props: { value: VALUE } }).findAll('rect')
    document.documentElement.removeAttribute('data-theme')
    expect(rects[0]?.classes()).toEqual(['fill-white'])
    expect(rects.slice(1).every((rect) => rect.classes().join() === 'fill-qr-dark')).toBe(true)
  })
})
