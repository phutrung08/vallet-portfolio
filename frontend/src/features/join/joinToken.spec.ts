import { describe, expect, it } from 'vitest'
import { extractToken } from '@/features/join/joinToken'

const TOKEN = 'Ab3_-xyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

describe('extractToken', () => {
  it.each([
    ['a full link', `https://vallet.example/join#${TOKEN}`],
    ['a fragment', `#${TOKEN}`],
    ['a bare token', TOKEN],
    ['a link with surrounding spaces', `  https://x.example/join#${TOKEN}\n`],
  ])('finds the token in %s', (_name, input) => {
    expect(extractToken(input)).toBe(TOKEN)
  })

  it.each([
    ['nothing', ''],
    ['only a hash', '#'],
    ['a link without a fragment', 'https://vallet.example/join'],
    ['a token with odd characters', 'abc def'],
    ['a token that is too long', 'a'.repeat(65)],
  ])('rejects %s', (_name, input) => {
    expect(extractToken(input)).toBeNull()
  })
})
