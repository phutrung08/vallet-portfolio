import type { CurrencyCode } from '@/lib/format'

export const MAX_TRIP_NAME = 80
export const MAX_PERSON_NAME = 40
export const MAX_OTHER_MEMBERS = 49

export type ErrorKey =
  | 'nameRequired'
  | 'nameTooLong'
  | 'personRequired'
  | 'personTooLong'
  | 'duplicate'
  | 'tooMany'
  | 'endBeforeStart'
  | 'invalid'

export interface TripForm {
  name: string
  startsOn: string
  endsOn: string
  usesFund: boolean
  currency: CurrencyCode
  creatorName: string
  memberNames: string[]
}

export type FormErrors = Partial<Record<'name' | 'dates' | 'creatorName' | 'members', ErrorKey>>

/** Same normalisation as the backend: NFC, collapsed whitespace runs, trimmed. */
export function normaliseName(raw: string): string {
  return raw.normalize('NFC').replace(/\s+/g, ' ').trim()
}

export function sameName(a: string, b: string): boolean {
  return a.toLowerCase().normalize('NFC') === b.toLowerCase().normalize('NFC')
}

function codePointLength(text: string): number {
  return [...text].length
}

function personNameError(name: string): ErrorKey | undefined {
  if (name === '') return 'personRequired'
  return codePointLength(name) > MAX_PERSON_NAME ? 'personTooLong' : undefined
}

export function checkNewMember(
  raw: string,
  creatorName: string,
  names: readonly string[],
): { name: string } | { error: ErrorKey } {
  const name = normaliseName(raw)
  const error = personNameError(name)
  if (error) return { error }
  if (names.length >= MAX_OTHER_MEMBERS) return { error: 'tooMany' }
  const taken = [normaliseName(creatorName), ...names]
  if (taken.some((existing) => sameName(existing, name))) return { error: 'duplicate' }
  return { name }
}

export function validateTrip(form: TripForm): FormErrors {
  const errors: FormErrors = {}
  const name = normaliseName(form.name)
  if (name === '') errors.name = 'nameRequired'
  else if (codePointLength(name) > MAX_TRIP_NAME) errors.name = 'nameTooLong'

  if (form.startsOn !== '' && form.endsOn !== '' && form.endsOn < form.startsOn) {
    errors.dates = 'endBeforeStart'
  }

  const creator = normaliseName(form.creatorName)
  const creatorError = personNameError(creator)
  if (creatorError) errors.creatorName = creatorError
  else if (form.memberNames.some((member) => sameName(member, creator))) {
    errors.creatorName = 'duplicate'
  }

  if (form.memberNames.length > MAX_OTHER_MEMBERS) errors.members = 'tooMany'
  return errors
}

/** Maps backend validation paths such as "body.member_names.3" onto form error slots. */
export function serverFieldErrors(fields: readonly string[]): FormErrors {
  const errors: FormErrors = {}
  for (const path of fields) {
    const field = path.split('.')[1]
    if (field === 'name') errors.name = 'invalid'
    else if (field === 'creator_name') errors.creatorName = 'invalid'
    else if (field === 'member_names') errors.members = 'invalid'
    else if (field === 'starts_on' || field === 'ends_on') errors.dates = 'invalid'
  }
  return errors
}

export function buildCreateBody(form: TripForm) {
  return {
    name: normaliseName(form.name),
    currency: form.currency,
    ...(form.startsOn !== '' && { starts_on: form.startsOn }),
    ...(form.endsOn !== '' && { ends_on: form.endsOn }),
    uses_fund: form.usesFund,
    creator_name: normaliseName(form.creatorName),
    member_names: form.memberNames,
  }
}
