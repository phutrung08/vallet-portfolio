// Share tokens are URL-safe base64 (43 chars in production; backend rejects > 64 chars).
const TOKEN = /^[A-Za-z0-9_-]{1,64}$/

/** Extracts a valid share token from a full invite URL, fragment, or raw token string. */
export function extractToken(input: string): string | null {
  const text = input.trim()
  const hash = text.lastIndexOf('#')
  const candidate = hash === -1 ? text : text.slice(hash + 1)
  return TOKEN.test(candidate) ? candidate : null
}
