import { useI18n } from 'vue-i18n'
import { formatClock, formatDayMonthLocal } from '@/lib/format'
import type { AppLocale } from '@/lib/i18n'

const DAY_MS = 86_400_000

export interface Moment {
  time: string
  /** Localized day label ("today", "yesterday", or date string). */
  day: string
}

/** Format an ISO timestamp into local clock time and relative day string. */
export function useMoment(now: () => Date = () => new Date()) {
  const { t, locale } = useI18n()
  return (iso: string): Moment => {
    const at = new Date(iso)
    const today = new Date(now().getFullYear(), now().getMonth(), now().getDate())
    const startOfAt = new Date(at.getFullYear(), at.getMonth(), at.getDate())
    const daysAgo = Math.round((today.getTime() - startOfAt.getTime()) / DAY_MS)
    const where = locale.value as AppLocale
    let day = formatDayMonthLocal(at, where)
    if (daysAgo === 0) day = t('common.today')
    else if (daysAgo === 1) day = t('common.yesterday')
    return { time: formatClock(at, where), day }
  }
}
