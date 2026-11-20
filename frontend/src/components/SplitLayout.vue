<script setup lang="ts">
import { useTemplateRef } from 'vue'

/*
 * Two-pane page layout: list left, detail right, alongside the nav (styles/split.css).
 * From the split breakpoint or across a vertical hinge both panes display and scroll independently;
 * narrower screens render whichever pane `show` selects. Screens without nav pass `:nav="false"`.
 */
withDefaults(defineProps<{ show?: 'list' | 'detail'; nav?: boolean }>(), { show: 'list', nav: true })

const pane = 'split-pane flex min-w-0 flex-col gap-4 p-4 pb-nav'
const list = useTemplateRef('list-pane')
// Exposes the scrolling list pane so pull-to-refresh can attach directly.
defineExpose({ listPane: list })
</script>

<template>
  <main :class="['split-layout', !nav && 'split-no-nav']">
    <div
      ref="list-pane"
      :class="[pane, 'split-list', show !== 'list' && 'split-away']"
    >
      <slot name="list" />
    </div>
    <div :class="[pane, 'split-detail', show !== 'detail' && 'split-away']">
      <slot name="detail" />
    </div>
  </main>
</template>
