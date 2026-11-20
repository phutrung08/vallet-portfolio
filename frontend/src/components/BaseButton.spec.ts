import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from './BaseButton.vue'

describe('BaseButton', () => {
  it('renders the slot inside a native button of type button', () => {
    const wrapper = mount(BaseButton, { slots: { default: 'Save' } })
    expect(wrapper.element.tagName).toBe('BUTTON')
    expect(wrapper.text()).toBe('Save')
    expect(wrapper.attributes('type')).toBe('button')
  })

  it('uses the primary variant by default', () => {
    expect(mount(BaseButton).classes()).toContain('bg-yellow')
  })

  it.each([
    ['success', 'bg-green'],
    ['dark', 'bg-ink'],
    ['outline', 'bg-surface'],
    ['danger', 'bg-danger'],
    ['danger-outline', 'text-danger'],
  ] as const)('applies the %s variant fill', (variant, cls) => {
    expect(mount(BaseButton, { props: { variant } }).classes()).toContain(cls)
  })

  it('puts dark ink on the success fill', () => {
    expect(mount(BaseButton, { props: { variant: 'success' } }).classes()).toContain('text-on-green')
  })

  it('goes full width when block', () => {
    expect(mount(BaseButton, { props: { block: true } }).classes()).toContain('w-full')
    expect(mount(BaseButton).classes()).not.toContain('w-full')
  })

  it('supports type submit', () => {
    expect(mount(BaseButton, { props: { type: 'submit' } }).attributes('type')).toBe('submit')
  })

  it('emits click when enabled', async () => {
    const wrapper = mount(BaseButton)
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('has the disabled attribute and emits no click when disabled', async () => {
    const wrapper = mount(BaseButton, { props: { disabled: true } })
    expect(wrapper.attributes('disabled')).toBeDefined()
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })
})
