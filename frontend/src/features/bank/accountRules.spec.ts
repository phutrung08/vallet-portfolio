import { describe, expect, it } from 'vitest'
import type { Bank } from '@/entities'
import {
  digitsOnly,
  filterBanks,
  finalAccountName,
  stripDiacritics,
  typedAccountName,
  validateAccount,
} from '@/features/bank/accountRules'

const banks: Bank[] = [
  { bin: '970436', code: 'VCB', short_name: 'Vietcombank' },
  { bin: '970415', code: 'ICB', short_name: 'VietinBank' },
  { bin: '971025', code: 'momo', short_name: 'MoMo' },
  { bin: '970422', code: 'MB', short_name: 'MBBank' },
]

describe('stripDiacritics', () => {
  it('folds Latin and Vietnamese diacritics including stroked D', () => {
    expect(stripDiacritics('Nguyễn Văn Đức đ')).toBe('Nguyen Van Duc d')
  })
})

describe('digitsOnly', () => {
  it('strips non-digits and clamps to 19 characters', () => {
    expect(digitsOnly('0123 456-789 abc')).toBe('0123456789')
    expect(digitsOnly('1'.repeat(30))).toHaveLength(19)
  })
})

describe('account name formatting', () => {
  it('normalises typing to uppercase ASCII while collapsing repeated spaces', () => {
    expect(typedAccountName('  nguyễn   văn đức ')).toBe('NGUYEN VAN DUC ')
  })

  it('trims trailing whitespace in finalAccountName', () => {
    expect(finalAccountName('  Trần  Thị Hợp ')).toBe('TRAN THI HOP')
  })
})

describe('validateAccount', () => {
  const valid = { bin: '970436', number: '0123456789', name: 'Alex Rivera' }

  it('accepts a valid BIN, 6-to-19-digit account number, and Latin name', () => {
    expect(validateAccount(valid)).toEqual({})
    expect(validateAccount({ ...valid, number: '123456' })).toEqual({})
    expect(validateAccount({ ...valid, number: '1'.repeat(19) })).toEqual({})
  })

  it('reports field errors for missing BIN, invalid digits, and invalid holder names', () => {
    expect(validateAccount({ ...valid, bin: null }).bank).toBe('bankRequired')
    expect(validateAccount({ ...valid, number: '12345' }).number).toBe('numberInvalid')
    expect(validateAccount({ ...valid, name: '' }).name).toBe('nameInvalid')
    expect(validateAccount({ ...valid, name: 'Alex 2' }).name).toBe('nameInvalid')
    expect(validateAccount({ ...valid, name: 'A'.repeat(51) }).name).toBe('nameInvalid')
  })
})

describe('filterBanks', () => {
  const codes = (query: string) => filterBanks(banks, query).map((bank) => bank.code)

  it('returns all banks for whitespace-only queries', () => {
    expect(codes('  ')).toHaveLength(4)
  })

  it('matches short name and code case-insensitively', () => {
    expect(codes('vietin')).toEqual(['ICB'])
    expect(codes('vcb')).toEqual(['VCB'])
    expect(codes('MBB')).toEqual(['MB'])
  })

  it('matches queries with or without accents', () => {
    expect(codes('Việt')).toEqual(['VCB', 'ICB'])
    expect(codes('viet')).toEqual(['VCB', 'ICB'])
    expect(codes('MÔMO')).toEqual(['momo'])
  })

  it('returns empty array when no bank matches', () => {
    expect(codes('zzz')).toEqual([])
  })
})
