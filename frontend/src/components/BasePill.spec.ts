import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BasePill from './BasePill.vue'

describe('BasePill', () => {
  it('renders the slot in a span with the neutral tone by default', () => {
    const wrapper = mount(BasePill, { slots: { default: 'Paid' } })
    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.text()).toBe('Paid')
    expect(wrapper.classes()).toContain('bg-surface')
  })

  it.each([
    ['green', 'bg-green-soft'],
    ['yellow', 'bg-yellow-soft'],
    ['sky', 'bg-sky-soft'],
    ['danger', 'bg-danger-soft'],
  ] as const)('applies the %s tone', (tone, cls) => {
    expect(mount(BasePill, { props: { tone } }).classes()).toContain(cls)
  })

  it('overrides the tone when selected', () => {
    const classes = mount(BasePill, { props: { tone: 'green', selected: true } }).classes()
    expect(classes).toContain('bg-ink')
    expect(classes).not.toContain('bg-green-soft')
  })
})
