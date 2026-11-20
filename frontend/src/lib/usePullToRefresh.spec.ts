import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { effectScope, nextTick, shallowRef } from 'vue'
import { PULL_THRESHOLD, usePullToRefresh } from '@/lib/usePullToRefresh'

let element: HTMLElement

function touch(type: string, clientY?: number): void {
  const event = new Event(type)
  Object.defineProperty(event, 'touches', { value: clientY === undefined ? [] : [{ clientY }] })
  element.dispatchEvent(event)
}

function pull(distance: number): void {
  touch('touchstart', 100)
  touch('touchmove', 100 + distance / 2)
  touch('touchmove', 100 + distance)
  touch('touchend')
}

function setScroll(y: number): void {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true })
}

function setup(onRefresh = vi.fn(() => Promise.resolve())) {
  const scope = effectScope()
  const result = scope.run(() => usePullToRefresh(shallowRef(element), onRefresh))
  if (!result) throw new Error('no result')
  return { ...result, onRefresh, scope }
}

beforeEach(() => {
  element = document.createElement('main')
  setScroll(0)
})

afterEach(() => {
  setScroll(0)
})

describe('usePullToRefresh', () => {
  it('refreshes once a pull passes the threshold', async () => {
    const { onRefresh, offset, armed } = setup()
    touch('touchstart', 100)
    touch('touchmove', 100 + PULL_THRESHOLD)
    expect(armed.value).toBe(true)
    expect(offset.value).toBe(PULL_THRESHOLD / 2)
    touch('touchend')
    await flushPromises()
    expect(onRefresh).toHaveBeenCalledTimes(1)
    expect(offset.value).toBe(0)
  })

  it('does nothing for a pull shorter than the threshold', async () => {
    const { onRefresh, armed } = setup()
    pull(PULL_THRESHOLD - 1)
    await flushPromises()
    expect(armed.value).toBe(false)
    expect(onRefresh).not.toHaveBeenCalled()
  })

  it('only starts when the page is scrolled to the top', async () => {
    const { onRefresh } = setup()
    setScroll(40)
    pull(PULL_THRESHOLD * 2)
    await flushPromises()
    expect(onRefresh).not.toHaveBeenCalled()
  })

  it('only starts when its own pane is scrolled to the top (split layouts)', async () => {
    const { onRefresh } = setup()
    element.scrollTop = 40
    pull(PULL_THRESHOLD * 2)
    await flushPromises()
    expect(onRefresh).not.toHaveBeenCalled()
  })

  it('gives up when the page scrolls during the pull', async () => {
    const { onRefresh } = setup()
    touch('touchstart', 100)
    setScroll(10)
    touch('touchmove', 100 + PULL_THRESHOLD * 2)
    touch('touchend')
    await flushPromises()
    expect(onRefresh).not.toHaveBeenCalled()
  })

  it('ignores pulls and button presses while a refresh is running', async () => {
    let finish: () => void = () => {}
    const onRefresh = vi.fn(() => new Promise<void>((resolve) => (finish = resolve)))
    const { refresh, refreshing } = setup(onRefresh)
    pull(PULL_THRESHOLD)
    await nextTick()
    expect(refreshing.value).toBe(true)
    pull(PULL_THRESHOLD)
    await refresh()
    expect(onRefresh).toHaveBeenCalledTimes(1)
    finish()
    await flushPromises()
    expect(refreshing.value).toBe(false)
  })

  it('stops listening when its scope ends', async () => {
    const { onRefresh, scope } = setup()
    scope.stop()
    pull(PULL_THRESHOLD * 2)
    await flushPromises()
    expect(onRefresh).not.toHaveBeenCalled()
  })
})
