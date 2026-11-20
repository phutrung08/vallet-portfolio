import type { Expense, SplitMode, TripMember } from '@/entities'
import { allocate } from '@/features/expenses/allocate'

export const FULL_BASIS_POINTS = 10_000
export const MAX_SHARES = 10_000

/** Client-side split editor state preserving per-mode inputs while switching modes. */
export interface SplitDraft {
  mode: SplitMode
  /** Selected participant IDs (sorted by trip position before submission). */
  included: string[]
  /** Share weights per member; unset defaults to 1. */
  shares: Record<string, number>
  /** Percentage weights in basis points (10 000 = 100%). */
  basisPoints: Record<string, number | null>
  /** Explicit minor-unit amounts per member. */
  amounts: Record<string, number | null>
}

export type SplitRequest =
  | { mode: 'equal'; participants: string[] }
  | { mode: 'shares'; shares: Record<string, number> }
  | { mode: 'percent'; basis_points: Record<string, number> }
  | { mode: 'exact'; amounts: Record<string, number> }

/** Validation issue with the current split configuration. */
export type SplitProblem =
  | { key: 'noParticipants' | 'sharesZero' }
  | { key: 'missing' | 'excess'; amount: number }
  | { key: 'missing' | 'excess'; percent: number }

export function initialDraft(candidates: readonly TripMember[]): SplitDraft {
  return {
    mode: 'equal',
    included: candidates.filter((member) => !member.removed).map((member) => member.id),
    shares: {},
    basisPoints: {},
    amounts: {},
  }
}

/** Reconstructs an editable split draft from a stored expense. */
export function draftFromExpense(expense: Expense): SplitDraft {
  const weights = Object.fromEntries(expense.shares.map((share) => [share.member_id, share.weight]))
  const mode = expense.split_mode
  return {
    mode,
    included: expense.shares.map((share) => share.member_id),
    shares: mode === 'shares' ? weights : {},
    basisPoints: mode === 'percent' ? weights : {},
    amounts: mode === 'exact' ? weights : {},
  }
}

export function toggled(included: readonly string[], id: string): string[] {
  return included.includes(id) ? included.filter((other) => other !== id) : [...included, id]
}

/** Included participants sorted by trip position to match backend ordering. */
export function participants(draft: SplitDraft, candidates: readonly TripMember[]): TripMember[] {
  return candidates
    .filter((member) => draft.included.includes(member.id))
    .sort((a, b) => a.position - b.position)
}

/** Active weight or amount for `id` under the current split mode. */
export function weightOf(draft: SplitDraft, id: string): number | null {
  if (draft.mode === 'equal') return 1
  if (draft.mode === 'shares') return draft.shares[id] ?? 1
  if (draft.mode === 'percent') return draft.basisPoints[id] ?? null
  return draft.amounts[id] ?? null
}

/** Sum of participant weights (shares, basis points, or minor units) in current mode. */
export function weightTotal(draft: SplitDraft, candidates: readonly TripMember[]): number {
  return participants(draft, candidates).reduce((sum, member) => sum + (weightOf(draft, member.id) ?? 0), 0)
}

/** Builds the API `split` request payload, omitting null fields in percent/exact modes. */
export function buildSplit(draft: SplitDraft, candidates: readonly TripMember[]): SplitRequest {
  const ids = participants(draft, candidates).map((member) => member.id)
  if (draft.mode === 'equal') return { mode: 'equal', participants: ids }
  const weights: Record<string, number> = {}
  for (const id of ids) {
    const weight = weightOf(draft, id)
    if (weight !== null) weights[id] = weight
  }
  if (draft.mode === 'shares') return { mode: 'shares', shares: weights }
  if (draft.mode === 'percent') return { mode: 'percent', basis_points: weights }
  return { mode: 'exact', amounts: weights }
}

export function splitProblem(
  draft: SplitDraft,
  candidates: readonly TripMember[],
  amount: number | null,
): SplitProblem | null {
  if (participants(draft, candidates).length === 0) return { key: 'noParticipants' }
  const total = weightTotal(draft, candidates)
  if (draft.mode === 'shares' && total === 0) return { key: 'sharesZero' }
  if (draft.mode === 'percent' && total !== FULL_BASIS_POINTS) {
    const gap = FULL_BASIS_POINTS - total
    return gap > 0 ? { key: 'missing', percent: gap } : { key: 'excess', percent: -gap }
  }
  if (draft.mode === 'exact' && amount !== null && total !== amount) {
    const gap = amount - total
    return gap > 0 ? { key: 'missing', amount: gap } : { key: 'excess', amount: -gap }
  }
  return null
}

/**
 * Computes exact per-participant share previews matching backend allocation; returns null while
 * the total amount or split constraints are incomplete.
 */
export function previewAmounts(
  draft: SplitDraft,
  candidates: readonly TripMember[],
  amount: number | null,
): Map<string, number> | null {
  if (amount === null || amount < 1 || splitProblem(draft, candidates, amount) !== null) return null
  const ids = participants(draft, candidates).map((member) => member.id)
  const weights = ids.map((id) => weightOf(draft, id) ?? 0)
  const parts = draft.mode === 'exact' ? weights : allocate(amount, weights)
  return new Map(ids.map((id, index) => [id, parts[index] ?? 0]))
}
