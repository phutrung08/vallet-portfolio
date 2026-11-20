import { afterEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { dialog } from '@/lib/domTestHelpers'
import BottomSheet from '@/components/BottomSheet.vue'

const wrappers: VueWrapper[] = []

function mountSheet(open: boolean, slotHtml = '<button id="inside" type="button">Inside</button>', title = 'Add expense') {
  const wrapper = mount(BottomSheet, {
    props: { open, title },
    slots: { default: slotHtml },
    attachTo: document.body,
  })
  wrappers.push(wrapper)
  return wrapper
}

const panel = () => dialog()?.querySelector<HTMLElement>('.bottom-sheet-panel') ?? null

function dispatchPointer(target: EventTarget, type: string, clientX: number, clientY: number) {
  const PointerCtor = window.PointerEvent ?? MouseEvent
  target.dispatchEvent(new PointerCtor(type, { bubbles: true, cancelable: true, clientX, clientY }))
}

afterEach(() => {
  while (wrappers.length > 0) {
    wrappers.pop()?.unmount()
  }
  document.body.style.overflow = ''
  document.body.innerHTML = ''
})

describe('BottomSheet', () => {
  it('renders nothing when closed', () => {
    mountSheet(false)
    expect(dialog()).toBeNull()
  })

  it('renders a native open <dialog> with title and slot content when open', () => {
    mountSheet(true)
    const dlg = dialog()
    expect(dlg?.tagName).toBe('DIALOG')
    expect(dlg?.hasAttribute('open')).toBe(true)
    expect(panel()?.textContent).toContain('Add expense')
    expect(panel()?.querySelector('#inside')).not.toBeNull()
  })

  it('exposes native dialog semantics labelled by the title without redundant role or aria-modal', () => {
    mountSheet(true)
    const dlg = dialog()
    expect(dlg?.classList).toContain('sheet-dialog')
    expect(dlg?.hasAttribute('role')).toBe(false)
    expect(dlg?.hasAttribute('aria-modal')).toBe(false)
    const id = dlg?.getAttribute('aria-labelledby') ?? ''
    expect(document.getElementById(id)?.textContent).toBe('Add expense')
    expect(panel()?.classList).toContain('bottom-sheet-panel')
    expect(panel()?.querySelector('.sheet-handle')?.getAttribute('aria-hidden')).toBe('true')
  })

  it('emits close on backdrop click or outside pointer press+release, not on panel click', () => {
    const wrapper = mountSheet(true)
    const dlg = dialog()!
    const pnl = panel()!
    pnl.querySelector<HTMLElement>('#inside')?.click()
    pnl.click()
    expect(wrapper.emitted('close')).toBeUndefined()

    dlg.click()
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('does not dismiss when pointerdown starts inside the panel and releases on the backdrop', () => {
    const wrapper = mountSheet(true)
    const dlg = dialog()!
    const pnl = panel()!
    pnl.getBoundingClientRect = () =>
      ({ left: 100, top: 100, right: 300, bottom: 300, width: 200, height: 200, x: 100, y: 100, toJSON: () => ({}) })

    dispatchPointer(pnl, 'pointerdown', 150, 150)
    dispatchPointer(dlg, 'pointerup', 20, 20)
    dlg.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 20, clientY: 20 }))
    expect(wrapper.emitted('close')).toBeUndefined()

    dispatchPointer(dlg, 'pointerdown', 20, 20)
    dispatchPointer(dlg, 'pointerup', 25, 25)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits close on Escape keydown and native cancel events', () => {
    const wrapper = mountSheet(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
    expect(wrapper.emitted('close')).toHaveLength(1)

    const cancelEvt = new Event('cancel', { cancelable: true })
    dialog()?.dispatchEvent(cancelEvt)
    expect(cancelEvt.defaultPrevented).toBe(true)
  })

  it('routes Escape and Tab strictly to the topmost stacked modal (LIFO)', async () => {
    const sheetA = mountSheet(true, '<button id="btn-a" type="button">A</button>', 'First sheet')
    const sheetB = mountSheet(true, '<button id="btn-b" type="button">B</button>', 'Second sheet')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
    expect(sheetB.emitted('close')).toHaveLength(1)
    expect(sheetA.emitted('close')).toBeUndefined()

    const btnB = document.getElementById('btn-b')!
    btnB.focus()
    const tab = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true })
    document.dispatchEvent(tab)
    expect(tab.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(btnB)

    await sheetB.setProps({ open: false })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
    expect(sheetA.emitted('close')).toHaveLength(1)
  })

  it('moves focus into the panel (or autofocus target) and restores opener focus on close', async () => {
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()

    const wrapper = mountSheet(false)
    await wrapper.setProps({ open: true })
    await wrapper.vm.$nextTick()
    expect(document.activeElement).toBe(panel())

    await wrapper.setProps({ open: false })
    expect(document.activeElement).toBe(opener)
  })

  it('focuses an element marked autofocus when opened', async () => {
    const wrapper = mountSheet(true, '<button id="primary" type="button">OK</button><button id="safe" type="button" autofocus>Cancel</button>')
    await wrapper.vm.$nextTick()
    expect(document.activeElement).toBe(document.getElementById('safe'))
  })

  it('traps Tab and Shift+Tab within the panel', async () => {
    const wrapper = mountSheet(true, '<button id="first" type="button">First</button><button id="last" type="button">Last</button>')
    await wrapper.vm.$nextTick()
    const first = document.getElementById('first')!
    const last = document.getElementById('last')!

    last.focus()
    const forwardTab = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true })
    document.dispatchEvent(forwardTab)
    expect(forwardTab.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(first)

    const backwardTab = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true })
    document.dispatchEvent(backwardTab)
    expect(backwardTab.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(last)
  })

  it('never mutates document.body.style.overflow while open or on unmount', async () => {
    const wrapper = mountSheet(true)
    expect(document.body.style.overflow).toBe('')
    await wrapper.setProps({ open: false })
    expect(document.body.style.overflow).toBe('')
    await wrapper.setProps({ open: true })
    expect(document.body.style.overflow).toBe('')
    wrapper.unmount()
    expect(document.body.style.overflow).toBe('')
  })
})
