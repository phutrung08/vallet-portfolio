import { vi } from 'vitest'

/** Stubs `window.matchMedia` to simulate wide split-layout vs narrow mobile viewports in tests. */
export function mockSplit(wide: boolean): void {
  vi.stubGlobal('matchMedia', () => ({
    matches: wide,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
}
