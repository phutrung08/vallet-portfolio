import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/styles/tokens.css'), 'utf8')
const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')

describe('design tokens and color-scheme setup', () => {
  it('declares light dark color-scheme in HTML and root tokens', () => {
    expect(html).toContain('<meta name="color-scheme" content="light dark" />')
    expect(css).toContain('color-scheme: light dark;')
    expect(css).toContain(':root[data-theme="light"]')
    expect(css).toContain(':root[data-theme="dark"]')
  })

  it('defines responsive layout breakpoints and shadows', () => {
    expect(css).toContain('--breakpoint-rail: 37.5rem')
    expect(css).toContain('--breakpoint-split: 42rem')
    expect(css).toContain('--breakpoint-phone-lg: 25rem')
    expect(css).toContain('@utility ink-border')
    expect(css).toContain('@utility card-ink')
  })

  it('keeps focused elements clear of bottom chrome and wraps long words cleanly', () => {
    expect(css).toContain('scroll-padding-bottom:')
    expect(css).toContain('overflow-wrap: break-word;')
    expect(css).toContain('text-wrap: balance;')
  })
})
