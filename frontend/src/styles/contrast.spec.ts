import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/styles/tokens.css'), 'utf8')

type Palette = Record<string, string>

function declarations(block: string): Palette {
  const out: Palette = {}
  for (const m of block.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})\s*;/gi)) out[m[1]!] = m[2]!
  return out
}

function blockAfter(marker: string): string {
  const start = css.indexOf(marker)
  const end = css.indexOf('\n}', start)
  return css.slice(start, end)
}

const fixed = declarations(blockAfter('@theme {'))
const light: Palette = { ...fixed, ...declarations(blockAfter(':root {')) }
const dark: Palette = { ...fixed, ...declarations(blockAfter(':root[data-theme="dark"]')) }

function channel(hex: string, at: number): number {
  const v = parseInt(hex.slice(at, at + 2), 16) / 255
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  return 0.2126 * channel(hex, 1) + 0.7152 * channel(hex, 3) + 0.0722 * channel(hex, 5)
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

function pick(palette: Palette, name: string): string {
  const hex = palette[`c-${name}`] ?? palette[`color-${name}`]
  if (!hex) throw new Error(`Unknown token ${name}`)
  return hex
}

const pairs: [string, string][] = [
  ['ink', 'cream'],
  ['ink', 'surface'],
  ['ink', 'sand'],
  ['ink', 'green-soft'],
  ['ink', 'yellow-soft'],
  ['ink', 'sky-soft'],
  ['muted', 'cream'],
  ['muted', 'surface'],
  ['muted', 'sand'],
  ['green-ink', 'cream'],
  ['green-ink', 'surface'],
  ['green-ink', 'green-soft'],
  ['danger', 'cream'],
  ['danger', 'surface'],
  ['danger', 'danger-soft'],
  ['on-accent', 'ink'],
  ['on-accent', 'danger'],
  ['on-green', 'green'],
  ['on-yellow', 'yellow'],
]

describe.each([
  ['light', light],
  ['dark', dark],
] as const)('%s theme contrast', (_theme, palette) => {
  it.each(pairs)('%s on %s is at least 4.5:1', (fg, bg) => {
    expect(ratio(pick(palette, fg), pick(palette, bg))).toBeGreaterThanOrEqual(4.5)
  })
})

describe('dark theme blocks', () => {
  it('system-dark block matches the explicit dark block', () => {
    const explicit = declarations(blockAfter(':root[data-theme="dark"]'))
    const system = declarations(blockAfter(':root:not([data-theme])'))
    expect(system).toEqual(explicit)
  })
})
