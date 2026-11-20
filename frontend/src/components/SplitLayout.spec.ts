import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SplitLayout from '@/components/SplitLayout.vue'

const slots = { list: '<p>List</p>', detail: '<p>Detail</p>' }

function panes(show?: 'list' | 'detail', nav?: boolean) {
  const wrapper = mount(SplitLayout, {
    props: {
      ...(show !== undefined ? { show } : {}),
      ...(nav !== undefined ? { nav } : {}),
    },
    slots,
  })
  return { wrapper, list: wrapper.get('.split-list'), detail: wrapper.get('.split-detail') }
}

describe('SplitLayout', () => {
  it('renders list left of detail inside main landmark', () => {
    const { wrapper, list, detail } = panes()
    expect(wrapper.element.tagName).toBe('MAIN')
    expect(wrapper.classes()).toContain('split-layout')
    expect(wrapper.classes()).not.toContain('split-no-nav')
    expect(list.text()).toBe('List')
    expect(detail.text()).toBe('Detail')
    expect(wrapper.element.firstElementChild).toBe(list.element)
  })

  it('adds split-no-nav when nav is false', () => {
    const { wrapper } = panes(undefined, false)
    expect(wrapper.classes()).toContain('split-no-nav')
  })

  it('shows the list pane on single-column viewports by default', () => {
    const { list, detail } = panes()
    expect(list.classes()).not.toContain('split-away')
    expect(detail.classes()).toContain('split-away')
  })

  it('shows the detail pane when requested', () => {
    const { list, detail } = panes('detail')
    expect(list.classes()).toContain('split-away')
    expect(detail.classes()).not.toContain('split-away')
  })

  it('gives both panes independent scroll, padding, and dock clearance classes', () => {
    const { list, detail } = panes()
    for (const pane of [list, detail]) {
      expect(pane.classes()).toEqual(expect.arrayContaining(['split-pane', 'p-4', 'pb-nav']))
    }
  })

  it('exposes listPane ref for pull-to-refresh binding', () => {
    const { wrapper, list } = panes()
    expect((wrapper.vm as unknown as { listPane: HTMLElement }).listPane).toBe(list.element)
  })
})
