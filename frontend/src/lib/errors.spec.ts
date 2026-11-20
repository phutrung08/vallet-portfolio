import { describe, expect, it } from 'vitest'
import { ApiError } from '@/lib/api'
import { errorMessageKey } from '@/lib/errors'
import enRaw from '@/locales/en.json?raw'

const enErrors = Object.keys((JSON.parse(enRaw) as { errors: Record<string, string> }).errors).filter(
  (code) => code !== 'generic',
)

describe('errorMessageKey', () => {
  it.each(enErrors)('maps the documented locale error %s to its own key', (code) => {
    expect(errorMessageKey(new ApiError(400, code, 'x'))).toBe(`errors.${code}`)
  })

  it('falls back to the generic key for unknown codes and non-API errors', () => {
    expect(errorMessageKey(new ApiError(500, 'internal_error', 'x'))).toBe('errors.generic')
    expect(errorMessageKey(new Error('boom'))).toBe('errors.generic')
    expect(errorMessageKey(undefined)).toBe('errors.generic')
  })
})
