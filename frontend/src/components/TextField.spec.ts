import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TextField from './TextField.vue'

describe('TextField', () => {
  it('binds label and input id and forwards normalized input', async () => {
    const wrapper = mount(TextField, {
      props: {
        label: 'Account number',
        modelValue: '',
        normalise: (raw: string) => raw.replace(/\D+/g, ''),
      },
    })
    const label = wrapper.get('label')
    const input = wrapper.get('input')
    expect(label.attributes('for')).toBe(input.attributes('id'))
    expect(input.attributes('autocomplete')).toBe('off')

    input.element.value = '012a34'
    input.element.dispatchEvent(new InputEvent('input', { bubbles: true }))
    expect(input.element.value).toBe('01234')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['01234'])
  })

  it('skips rewriting during IME composition and applies on compositionend', () => {
    const wrapper = mount(TextField, {
      props: {
        label: 'Name',
        modelValue: '',
        normalise: (raw: string) => raw.trim().toUpperCase(),
      },
    })
    const input = wrapper.get('input')
    input.element.value = 'an '
    input.element.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }))
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    input.element.dispatchEvent(new Event('compositionend', { bubbles: true }))
    expect(input.element.value).toBe('AN')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['AN'])
  })

  it('sets aria-invalid, aria-describedby, and alert role when error is present', () => {
    const wrapper = mount(TextField, {
      props: { label: 'Trip name', modelValue: '', error: 'Enter a trip name' },
    })
    const input = wrapper.get('input')
    const errorEl = wrapper.get('[role="alert"]')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(input.attributes('aria-describedby')).toBe(errorEl.attributes('id'))
    expect(errorEl.text()).toBe('Enter a trip name')
  })
})
