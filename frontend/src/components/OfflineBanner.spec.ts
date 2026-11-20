import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import OfflineBanner from '@/components/OfflineBanner.vue'
import { createAppI18n } from '@/lib/i18n'

function setOnline(value: boolean): void {
  Object.defineProperty(navigator, 'onLine', { value, configurable: true })
}

afterEach(() => {
  setOnline(true)
})

describe('OfflineBanner', () => {
  it('appears inside its live region while offline and disappears when online', async () => {
    setOnline(true)
    const wrapper = mount(OfflineBanner, { global: { plugins: [createAppI18n('en')] } })
    expect(wrapper.get('[role="status"]').text()).toBe('')

    setOnline(false)
    window.dispatchEvent(new Event('offline'))
    await nextTick()
    expect(wrapper.get('[role="status"]').text()).toBe('Offline · showing the saved copy')

    setOnline(true)
    window.dispatchEvent(new Event('online'))
    await nextTick()
    expect(wrapper.text()).toBe('')
    wrapper.unmount()
  })
})
