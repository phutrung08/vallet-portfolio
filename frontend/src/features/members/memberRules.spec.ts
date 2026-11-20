import { describe, expect, it } from 'vitest'
import { checkMemberName } from '@/features/members/memberRules'
import { buildShareLink } from '@/features/members/shareLink'

describe('checkMemberName', () => {
  it('returns the normalised name', () => {
    expect(checkMemberName('  Jordan   Lee ', ['Alex'])).toEqual({ name: 'Jordan Lee' })
  })

  it('refuses empty, too long and duplicate names', () => {
    expect(checkMemberName('   ', [])).toEqual({ error: 'required' })
    expect(checkMemberName('a'.repeat(41), [])).toEqual({ error: 'tooLong' })
    expect(checkMemberName('a'.repeat(40), [])).toEqual({ name: 'a'.repeat(40) })
    expect(checkMemberName('alex', ['Alex'])).toEqual({ error: 'duplicate' })
  })
})

describe('buildShareLink', () => {
  it('keeps the token in the fragment', () => {
    const link = buildShareLink('https://vallet.example', 'tok_1')
    expect(link).toBe('https://vallet.example/join#tok_1')
    expect(new URL(link).search).toBe('')
    expect(new URL(link).hash).toBe('#tok_1')
  })
})
