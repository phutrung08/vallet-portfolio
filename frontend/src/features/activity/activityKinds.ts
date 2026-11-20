import {
  Flag,
  Landmark,
  Link2,
  Lock,
  LockOpen,
  Pencil,
  PiggyBank,
  RotateCcw,
  UserMinus,
  UserPlus,
  Zap,
  type LucideIcon,
} from 'lucide-vue-next'

const KIND_ICONS: Record<string, LucideIcon> = {
  bank_account_set: Landmark,
  bank_account_removed: Landmark,
  fund_holder_changed: PiggyBank,
  fund_holder_assigned: PiggyBank,
  fund_holder_cleared: PiggyBank,
  member_added: UserPlus,
  member_joined: UserPlus,
  member_renamed: Pencil,
  member_removed: UserMinus,
  member_left: UserMinus,
  share_link_rotated: Link2,
  trip_locked: Lock,
  trip_unlocked: LockOpen,
  trip_closed: Flag,
  trip_reopened: RotateCcw,
}

export const iconForKind = (kind: string): LucideIcon => KIND_ICONS[kind] ?? Zap

/** Returns the i18n message key for a known event kind, falling back to generic copy. */
export const sentenceKey = (kind: string): string =>
  kind in KIND_ICONS ? `activity.kind.${kind}` : 'activity.kind.unknown'
