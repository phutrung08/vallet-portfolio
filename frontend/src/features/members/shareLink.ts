/**
 * Builds the trip invite URL with the token placed in the URL fragment so browsers
 * never transmit the secret token in HTTP requests or referrer headers.
 */
export function buildShareLink(origin: string, token: string): string {
  return `${origin}/join#${token}`
}
