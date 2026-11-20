/**
 * Port of backend `domain.money.allocate` so split previews match persisted shares.
 * Distributes `total` (integer minor units) across `weights` using exact BigInt arithmetic
 * and largest-remainder tie-breaking by lowest member index.
 */
export function allocate(total: number, weights: readonly number[]): number[] {
  if (!Number.isSafeInteger(total) || total < 0) throw new RangeError(`Invalid total: ${total}`)
  if (weights.length === 0) throw new RangeError('Weights must not be empty')
  if (weights.some((weight) => !Number.isSafeInteger(weight) || weight < 0)) {
    throw new RangeError(`Invalid weights: ${weights.join(', ')}`)
  }
  const big = weights.map(BigInt)
  const sum = big.reduce((acc, weight) => acc + weight, 0n)
  if (sum === 0n) {
    if (total > 0) throw new RangeError('Cannot allocate a positive total over zero weights')
    return weights.map(() => 0)
  }
  const amount = BigInt(total)
  const parts = big.map((weight) => (amount * weight) / sum)
  const remainders = big.map((weight) => (amount * weight) % sum)
  const leftover = Number(amount - parts.reduce((acc, part) => acc + part, 0n))
  const byRemainder = weights
    .map((_, index) => index)
    .sort((a, b) => {
      const [ra = 0n, rb = 0n] = [remainders[a], remainders[b]]
      if (ra !== rb) return ra > rb ? -1 : 1
      return a - b
    })
  for (const index of byRemainder.slice(0, leftover)) parts[index] = (parts[index] ?? 0n) + 1n
  return parts.map(Number)
}
