import type { Ref } from 'vue'
import { useMediaQuery } from '@/lib/useMediaQuery'

/** Split breakpoint from tokens.css, or a vertical hinge (each segment is one pane). */
export const SPLIT_QUERY = '(min-width: 42rem), (horizontal-viewport-segments: 2)'

/** Whether the two-pane split layout is active. */
export function useSplit(): Ref<boolean> {
  return useMediaQuery(SPLIT_QUERY)
}
