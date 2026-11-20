import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CachedNotice from '@/components/CachedNotice.vue'
import type { CachedCopy } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'

const now = () => new Date(2026, 10, 16, 18, 0)

function render(copy: CachedCopy | null) {
  return mount(CachedNotice, { props: { copy, now }, global: { plugins: [createAppI18n('en')] } })
}

describe('CachedNotice', () => {
  it('renders nothing for fresh network data', () => {
    expect(render(null).text()).toBe('')
  })

  it('shows when the cached copy was last updated', () => {
    expect(render({ savedAt: new Date(2026, 10, 16, 7, 5) }).text()).toBe('Updated at 07:05')
  })

  it('falls back to saved copy notice when timestamp is missing', () => {
    expect(render({ savedAt: null }).text()).toBe('Showing the saved copy')
  })
})
