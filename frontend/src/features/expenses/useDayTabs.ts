import { nextTick, ref, watch } from 'vue'
import type { DaySummary } from '@/entities'

/** Keyboard navigation and scroll-into-view behavior for day selection tabs. */
export function useDayTabs(
  days: () => readonly DaySummary[],
  selected: () => string | null,
  select: (date: string) => void,
) {
  const list = ref<HTMLElement>()

  function onKeydown(event: KeyboardEvent, index: number): void {
    const target = {
      ArrowLeft: index - 1,
      ArrowRight: index + 1,
      Home: 0,
      End: days().length - 1,
    }[event.key]
    const day = target === undefined ? undefined : days()[target]
    if (!day) return
    event.preventDefault()
    select(day.date)
  }

  watch(
    selected,
    async (date) => {
      await nextTick()
      const tab = [...(list.value?.children ?? [])].find((el) => el.id === `day-tab-${date}`)
      if (!(tab instanceof HTMLElement)) return
      // Keep roving focus synced onto the newly active tab when moving with arrow keys.
      if (list.value?.contains(document.activeElement)) tab.focus()
      tab.scrollIntoView({ inline: 'center', block: 'nearest' })
    },
    { immediate: true },
  )

  return { list, onKeydown }
}
