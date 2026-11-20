/**
 * Allocates integer percentages across `amounts` that sum to 100 using the largest-remainder
 * method so rounded shares never underflow or overflow the total bar width.
 */
export function percentsOf(amounts: readonly number[]): number[] {
  const total = amounts.reduce((sum, amount) => sum + amount, 0)
  if (total <= 0) return amounts.map(() => 0)
  const percents = amounts.map((amount) => Math.floor((amount * 100) / total))
  const leftover = 100 - percents.reduce((sum, percent) => sum + percent, 0)
  const byRemainder = amounts
    .map((amount, index) => ({ index, remainder: (amount * 100) % total, amount }))
    .sort((a, b) => b.remainder - a.remainder || b.amount - a.amount || a.index - b.index)
  for (const { index } of byRemainder.slice(0, leftover)) {
    percents[index] = (percents[index] ?? 0) + 1
  }
  return percents
}
