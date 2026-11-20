import { describe, expect, it } from 'vitest'
import {
  buildCreateBody,
  checkNewMember,
  normaliseName,
  serverFieldErrors,
  validateTrip,
  type TripForm,
} from '@/features/trips/tripFormRules'

const NFC = 'José'
const NFD = NFC.normalize('NFD')

function form(overrides: Partial<TripForm> = {}): TripForm {
  return {
    name: 'Da Lat Trip',
    startsOn: '',
    endsOn: '',
    usesFund: false,
    currency: 'VND',
    creatorName: 'Alex',
    memberNames: [],
    ...overrides,
  }
}

describe('normaliseName', () => {
  it('normalises to NFC, collapses whitespace runs, and trims', () => {
    expect(normaliseName(`  ${NFD} \t  Cruz  `)).toBe(`${NFC} Cruz`)
  })
})

describe('validateTrip', () => {
  it('accepts a minimal valid form', () => {
    expect(validateTrip(form())).toEqual({})
  })

  it('requires both names and enforces character limits', () => {
    expect(validateTrip(form({ name: '   ', creatorName: '' }))).toEqual({
      name: 'nameRequired',
      creatorName: 'personRequired',
    })
    expect(validateTrip(form({ name: 'a'.repeat(81), creatorName: 'b'.repeat(41) }))).toEqual({
      name: 'nameTooLong',
      creatorName: 'personTooLong',
    })
    expect(validateTrip(form({ name: 'a'.repeat(80), creatorName: 'b'.repeat(40) }))).toEqual({})
  })

  it('counts Unicode code points rather than UTF-16 code units', () => {
    expect(validateTrip(form({ creatorName: '😀'.repeat(40) }))).toEqual({})
  })

  it('rejects end dates before start date while allowing equal dates', () => {
    expect(validateTrip(form({ startsOn: '2026-11-08', endsOn: '2026-11-05' }))).toEqual({
      dates: 'endBeforeStart',
    })
    expect(validateTrip(form({ startsOn: '2026-11-05', endsOn: '2026-11-05' }))).toEqual({})
    expect(validateTrip(form({ endsOn: '2026-11-05' }))).toEqual({})
  })

  it('flags creator name collisions regardless of case or Unicode normalization', () => {
    expect(validateTrip(form({ creatorName: 'JOSÉ', memberNames: [NFC] }))).toEqual({
      creatorName: 'duplicate',
    })
    expect(validateTrip(form({ creatorName: NFD, memberNames: ['josé'] }))).toEqual({
      creatorName: 'duplicate',
    })
  })

  it('rejects more than 49 additional members', () => {
    const many = Array.from({ length: 50 }, (_, index) => `Person ${index}`)
    expect(validateTrip(form({ memberNames: many }))).toEqual({ members: 'tooMany' })
    expect(validateTrip(form({ memberNames: many.slice(1) }))).toEqual({})
  })
})

describe('checkNewMember', () => {
  it('returns the normalised name', () => {
    expect(checkNewMember(`  ${NFD}  `, 'Alex', [])).toEqual({ name: NFC })
  })

  it.each([
    ['empty', '   ', 'personRequired'],
    ['too long', 'x'.repeat(41), 'personTooLong'],
    ['creator duplicate by case', 'aLEX', 'duplicate'],
    ['member duplicate by NFD', NFD, 'duplicate'],
    ['member duplicate by case', 'josé', 'duplicate'],
  ])('rejects %s', (_label, raw, error) => {
    expect(checkNewMember(raw, 'Alex', [NFC])).toEqual({ error })
  })

  it('rejects adding a 50th other member', () => {
    const full = Array.from({ length: 49 }, (_, index) => `Person ${index}`)
    expect(checkNewMember('Extra', 'Alex', full)).toEqual({ error: 'tooMany' })
  })
})

describe('serverFieldErrors', () => {
  it('maps validation paths onto form slots and ignores unrelated fields', () => {
    expect(
      serverFieldErrors(['body.name', 'body.member_names.3', 'body.ends_on', 'body.currency']),
    ).toEqual({ name: 'invalid', members: 'invalid', dates: 'invalid' })
    expect(serverFieldErrors(['body.creator_name'])).toEqual({ creatorName: 'invalid' })
    expect(serverFieldErrors([])).toEqual({})
  })
})

describe('buildCreateBody', () => {
  it('omits empty dates and sends normalised names', () => {
    expect(buildCreateBody(form({ name: '  Da   Lat ', memberNames: ['Claire'] }))).toEqual({
      name: 'Da Lat',
      currency: 'VND',
      uses_fund: false,
      creator_name: 'Alex',
      member_names: ['Claire'],
    })
  })

  it('includes configured dates', () => {
    const body = buildCreateBody(form({ startsOn: '2026-11-05', endsOn: '2026-11-08' }))
    expect(body).toMatchObject({ starts_on: '2026-11-05', ends_on: '2026-11-08' })
  })
})
