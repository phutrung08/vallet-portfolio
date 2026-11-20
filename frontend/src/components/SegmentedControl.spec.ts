import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SegmentedControl from './SegmentedControl.vue'

describe('SegmentedControl', () => {
  const options = [
    { value: 'system', label: 'System' },
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
  ]

  it('exposes group label and pressed state per button', () => {
    const wrapper = mount(SegmentedControl, {
      props: { label: 'Appearance', options, modelValue: 'light' },
    })
    expect(wrapper.get('[role="group"]').attributes('aria-label')).toBe('Appearance')
    const buttons = wrapper.findAll('button')
    expect(buttons.map((b) => b.attributes('aria-pressed'))).toEqual(['false', 'true', 'false'])
  })

  it('emits selected option value when clicked', async () => {
    const wrapper = mount(SegmentedControl, {
      props: { label: 'Appearance', options, modelValue: 'system' },
    })
    await wrapper.findAll('button')[2]?.trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['dark'])
  })
})
