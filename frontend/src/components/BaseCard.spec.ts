import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseCard from './BaseCard.vue'

describe('BaseCard', () => {
  it('renders the slot in a div with surface tone, shadow and padding by default', () => {
    const wrapper = mount(BaseCard, { slots: { default: 'Hello' } })
    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.text()).toBe('Hello')
    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['bg-surface', 'shadow-hard', 'p-3', 'rounded-card']),
    )
  })

  it.each([
    ['green', 'bg-green'],
    ['yellow', 'bg-yellow-soft'],
    ['sky', 'bg-sky-soft'],
    ['sand', 'bg-sand'],
  ] as const)('applies the %s tone', (tone, cls) => {
    const wrapper = mount(BaseCard, { props: { tone } })
    expect(wrapper.classes()).toContain(cls)
    expect(wrapper.classes()).not.toContain('bg-surface')
  })

  it('drops the shadow when flat', () => {
    expect(mount(BaseCard, { props: { flat: true } }).classes()).not.toContain('shadow-hard')
  })

  it('renders the requested element tag', () => {
    expect(mount(BaseCard, { props: { as: 'section' } }).element.tagName).toBe('SECTION')
  })
})
