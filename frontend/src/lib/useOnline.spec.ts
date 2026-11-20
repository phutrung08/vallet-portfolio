import { afterEach, describe, expect, it } from 'vitest'
import { effectScope } from 'vue'
import { useOnline } from '@/lib/useOnline'

function setOnline(value: boolean): void {
  Object.defineProperty(navigator, 'onLine', { value, configurable: true })
}

afterEach(() => {
  setOnline(true)
})

describe('useOnline', () => {
  it('starts from navigator.onLine and follows the online and offline events', () => {
    setOnline(false)
    const scope = effectScope()
    const online = scope.run(() => useOnline())
    expect(online?.value).toBe(false)

    setOnline(true)
    window.dispatchEvent(new Event('online'))
    expect(online?.value).toBe(true)

    setOnline(false)
    window.dispatchEvent(new Event('offline'))
    expect(online?.value).toBe(false)
    scope.stop()
  })

  it('stops listening when its scope ends', () => {
    const scope = effectScope()
    const online = scope.run(() => useOnline())
    scope.stop()
    setOnline(false)
    window.dispatchEvent(new Event('offline'))
    expect(online?.value).toBe(true)
  })
})
