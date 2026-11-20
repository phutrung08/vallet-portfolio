import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const readCss = (file: string) => readFileSync(resolve(process.cwd(), 'src/styles', file), 'utf8')
const tokensCss = readCss('tokens.css')
const navCss = readCss('nav.css')
const splitCss = readCss('split.css')
const sheetCss = readCss('sheet.css')
const allCss = tokensCss + navCss + splitCss + sheetCss
const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')

describe('design tokens and color-scheme setup', () => {
  it('declares light dark color-scheme in HTML and root tokens', () => {
    expect(html).toContain('<meta name="color-scheme" content="light dark" />')
    expect(tokensCss).toContain('color-scheme: light dark;')
    expect(tokensCss).toContain(':root[data-theme="light"]')
    expect(tokensCss).toContain(':root[data-theme="dark"]')
  })

  it('defines responsive layout breakpoints and shadows', () => {
    expect(tokensCss).toContain('--breakpoint-rail: 37.5rem')
    expect(tokensCss).toContain('--breakpoint-split: 42rem')
    expect(tokensCss).toContain('--breakpoint-phone-lg: 25rem')
    expect(tokensCss).toContain('@utility ink-border')
    expect(tokensCss).toContain('@utility card-ink')
  })

  it('keeps focused elements clear of bottom chrome and wraps long words cleanly', () => {
    expect(tokensCss).toContain('scroll-padding-bottom:')
    expect(tokensCss).toContain('overflow-wrap: break-word;')
    expect(tokensCss).toContain('text-wrap: balance;')
  })

  it('uses native <dialog> sheets with backdrop scroll containment and reduced motion support', () => {
    expect(sheetCss).toContain('dialog.sheet-dialog:not([open])')
    expect(sheetCss).toContain('dialog.sheet-dialog::backdrop')
    expect(sheetCss).toContain('overscroll-behavior: contain;')
    expect(sheetCss).toMatch(/@media \(width >= theme\(--breakpoint-split\)\) \{\s+dialog\.sheet-dialog\[open\] \{\s+align-items: center;/)
    expect(sheetCss).toContain('border-radius: var(--radius-sheet)')
    expect(sheetCss).toMatch(/\.sheet-handle \{\s+display: none;/)
    expect(sheetCss).toContain('padding-left: max(1rem, env(viewport-segment-left 1 0))')
    expect(sheetCss).toContain('@media (horizontal-viewport-segments: 2)')
    expect(sheetCss).toMatch(/prefers-reduced-motion: reduce\) \{\s+\.sheet-enter-active/)
  })
})

describe('foldable viewport rules', () => {
  it('keeps the content column in the right segment of a vertical hinge', () => {
    expect(allCss).toContain('@media (horizontal-viewport-segments: 2)')
    expect(allCss).toContain('env(viewport-segment-left 1 0)')
    expect(allCss).toContain('env(viewport-segment-width 1 0)')
  })

  it('keeps content and nav above a horizontal fold and opens dialog sheets below it', () => {
    expect(navCss).toContain('@media (vertical-viewport-segments: 2)')
    expect(navCss).toContain('env(viewport-segment-bottom 0 0)')
    expect(navCss).toContain('dialog.sheet-dialog[open]')
    expect(navCss).toContain('env(viewport-segment-top 0 1)')
  })
})

describe('split layout rules', () => {
  it('splits list and detail from 42rem while hiding the inactive pane below it', () => {
    expect(splitCss).toContain('@media (width >= theme(--breakpoint-split))')
    expect(splitCss).toMatch(/@media \(width < theme\(--breakpoint-split\)\) \{\s+\.split-away \{\s+display: none;/)
    expect(splitCss).toContain('grid-template-columns: clamp(18.125rem, 43vw - 2.5rem, 25rem) minmax(0, 40rem)')
    expect(splitCss).toContain('justify-content: center')
  })

  it('places panes beside nav reserves and handles hinge and fold geometries', () => {
    expect(splitCss).toContain('margin-inline: var(--nav-reserve-left) var(--nav-reserve-right)')
    expect(splitCss).toContain('calc(env(viewport-segment-width 0 0) - var(--nav-reserve-left))')
    expect(splitCss).toContain('calc(env(viewport-segment-width 1 0) - var(--nav-reserve-right))')
    expect(splitCss).toContain('column-gap: calc(env(viewport-segment-left 1 0) - env(viewport-segment-right 0 0))')
    expect(splitCss).toContain('height: env(viewport-segment-bottom 0 0)')
    expect(splitCss).toContain('@utility col-center')
    expect(splitCss).toContain('width: min(28rem, env(viewport-segment-width 1 0) - 1.5rem)')
  })

  it('uses column #app layout so banners above split panes never overflow the viewport', () => {
    expect(splitCss).toMatch(/#app \{\s+display: flex;\s+flex-direction: column;/)
    expect(splitCss).toContain('flex: 1 1 0;')
  })
})

describe('navigation placement rules', () => {
  it.each(['bottom-left', 'bottom-right', 'edge-left', 'edge-right'])(
    'positions the phone dock for %s on large phones',
    (placement) => {
      expect(navCss).toContain(`nav[data-phone="${placement}"]`)
    },
  )

  it.each(['rail-left', 'rail-right'])('positions the wide rail for %s', (placement) => {
    expect(navCss).toContain(`nav[data-wide="${placement}"]`)
  })

  it('reserves the active side and narrows content by both reserves', () => {
    for (const attribute of [
      ':root[data-nav-phone="edge-left"]',
      ':root[data-nav-phone="edge-right"]',
      ':root[data-nav-wide="rail-right"]',
    ]) {
      expect(navCss).toContain(attribute)
    }
    expect(navCss).toContain('--nav-reserve-left')
    expect(navCss).toContain('--nav-reserve-right')
    expect(navCss).toContain('--nav-reserve-bottom: 0px')
    expect(navCss).toContain('width: min(28rem, 100% - var(--nav-reserve-left) - var(--nav-reserve-right))')
    expect(navCss).toContain('and (width < theme(--breakpoint-rail))')
    expect(navCss).toMatch(/nav\[data-phone\] \{\s+position: fixed;/)
    expect(navCss).toContain('prefers-reduced-motion: no-preference')
  })
})
