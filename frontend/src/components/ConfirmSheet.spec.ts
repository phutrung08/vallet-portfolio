import { afterEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { dialog } from '@/lib/domTestHelpers'
import { createAppI18n } from '@/lib/i18n'
import ConfirmSheet from '@/components/ConfirmSheet.vue'

let wrapper: VueWrapper | undefined

function mountConfirm(overrides: Partial<InstanceType<typeof ConfirmSheet>['$props']> = {}) {
  wrapper = mount(ConfirmSheet, {
    props: {
      open: true,
      title: 'Delete expense?',
      message: 'This removes it from the trip.',
      confirmLabel: 'Delete',
      ...overrides,
    },
    global: { plugins: [createAppI18n('en')] },
    attachTo: document.body,
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('ConfirmSheet', () => {
  it('renders message, error alert, and emits confirm/cancel', () => {
    mountConfirm({ error: 'Could not delete right now' })
    const dlg = dialog()!
    expect(dlg.textContent).toContain('This removes it from the trip.')
    expect(dlg.querySelector('[role="alert"]')?.textContent).toContain('Could not delete right now')

    const buttons = Array.from(dlg.querySelectorAll('button'))
    expect(buttons[0]?.textContent?.trim()).toBe('Delete')
    expect(buttons[1]?.textContent?.trim()).toBe('Cancel')

    buttons[0]?.click()
    buttons[1]?.click()
    expect(wrapper?.emitted('confirm')).toHaveLength(1)
    expect(wrapper?.emitted('cancel')).toHaveLength(1)
  })

  it('applies danger styling and focuses the safe Cancel action by default when danger is true', async () => {
    mountConfirm({ danger: true })
    await wrapper?.vm.$nextTick()
    const buttons = Array.from(dialog()!.querySelectorAll('button'))
    expect(buttons[0]?.className).toContain('bg-danger')
    expect(buttons[1]?.hasAttribute('autofocus')).toBe(true)
    expect(document.activeElement).toBe(buttons[1])
  })

  it('disables actions while pending is true', () => {
    mountConfirm({ pending: true })
    const buttons = Array.from(dialog()!.querySelectorAll('button'))
    expect(buttons.every((btn) => btn.disabled)).toBe(true)
  })
})
