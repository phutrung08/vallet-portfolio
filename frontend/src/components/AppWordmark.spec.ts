import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppWordmark from './AppWordmark.vue'

describe('AppWordmark', () => {
  it('is announced as one word and hides its two halves', () => {
    const wrapper = mount(AppWordmark)
    expect(wrapper.attributes('aria-label')).toBe('Vallet')
    const parts = wrapper.findAll('span[aria-hidden="true"]')
    expect(parts.map((part) => part.text())).toEqual(['val', 'let'])
  })

  it('defaults to the small size and supports md', () => {
    expect(mount(AppWordmark).classes()).toContain('text-[17px]')
    expect(mount(AppWordmark, { props: { size: 'md' } }).classes()).toContain('text-[22px]')
  })
})
