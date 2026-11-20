import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseAvatar from './BaseAvatar.vue'

const initialOf = (name: string) => mount(BaseAvatar, { props: { name } }).text()

describe('BaseAvatar', () => {
  it('shows the uppercased first letter', () => {
    expect(initialOf('binh')).toBe('B')
  })

  it('trims and uppercases Unicode letters', () => {
    expect(initialOf(' \u0111\u1ee9c ')).toBe('\u0110')
    expect(initialOf('\u0103n')).toBe('\u0102')
  })

  it('shows ? for empty or blank names', () => {
    expect(initialOf('')).toBe('?')
    expect(initialOf('   ')).toBe('?')
  })

  it('keeps a whole emoji as the initial', () => {
    expect(initialOf('\u{1F600} Tay')).toBe('\u{1F600}')
    const family = '\u{1F468}\u200D\u{1F469}\u200D\u{1F467}'
    expect(initialOf(`${family} family`)).toBe(family)
  })

  it('exposes the name as an image label', () => {
    const wrapper = mount(BaseAvatar, { props: { name: 'An' } })
    expect(wrapper.attributes('role')).toBe('img')
    expect(wrapper.attributes('aria-label')).toBe('An')
    expect(wrapper.attributes('aria-hidden')).toBeUndefined()
  })

  it('is hidden from assistive tech when the name is empty', () => {
    const wrapper = mount(BaseAvatar, { props: { name: ' ' } })
    expect(wrapper.attributes('aria-label')).toBeUndefined()
    expect(wrapper.attributes('aria-hidden')).toBe('true')
  })

  it('defaults to md size and green tone', () => {
    const classes = mount(BaseAvatar, { props: { name: 'a' } }).classes()
    expect(classes).toContain('size-7')
    expect(classes).toContain('bg-green-soft')
  })

  it.each([
    ['sm', 'size-6'],
    ['lg', 'size-[34px]'],
  ] as const)('applies the %s size', (size, cls) => {
    expect(mount(BaseAvatar, { props: { name: 'a', size } }).classes()).toContain(cls)
  })

  it.each([
    ['yellow', 'bg-yellow-soft'],
    ['sky', 'bg-sky-soft'],
    ['sand', 'bg-sand'],
  ] as const)('applies the %s tone', (tone, cls) => {
    expect(mount(BaseAvatar, { props: { name: 'a', tone } }).classes()).toContain(cls)
  })

  it('uses muted styling over the tone', () => {
    const classes = mount(BaseAvatar, { props: { name: 'a', muted: true } }).classes()
    expect(classes).toContain('text-muted')
    expect(classes).toContain('border-line')
    expect(classes).not.toContain('bg-green-soft')
  })
})
