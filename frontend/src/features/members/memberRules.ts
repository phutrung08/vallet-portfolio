import { MAX_PERSON_NAME, normaliseName, sameName } from '@/features/trips/tripFormRules'

export type NameError = 'required' | 'tooLong' | 'duplicate'

/** Validates a member display name against length and case-insensitive uniqueness rules. */
export function checkMemberName(
  raw: string,
  others: readonly string[],
): { name: string } | { error: NameError } {
  const name = normaliseName(raw)
  if (name === '') return { error: 'required' }
  if ([...name].length > MAX_PERSON_NAME) return { error: 'tooLong' }
  if (others.some((other) => sameName(other, name))) return { error: 'duplicate' }
  return { name }
}
