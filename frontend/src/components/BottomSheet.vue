<script setup lang="ts">
import { toRef, useId } from 'vue'
import { useModalBehavior } from '@/lib/useModalBehavior'

const props = defineProps<{
  open: boolean
  title: string
}>()

const emit = defineEmits<{ close: [] }>()

const titleId = useId()

const { dialogEl, panelEl, onAfterLeave } = useModalBehavior(toRef(props, 'open'), () => emit('close'))
</script>

<template>
  <Teleport to="body">
    <Transition
      name="sheet"
      @after-leave="onAfterLeave"
    >
      <dialog
        v-if="open"
        ref="dialogEl"
        class="sheet-dialog"
        :aria-labelledby="titleId"
        closedby="any"
      >
        <div
          ref="panelEl"
          tabindex="-1"
          class="bottom-sheet-panel bg-cream rounded-t-sheet border-edge max-h-[90dvh] w-full max-w-md overflow-y-auto overscroll-contain border-x-[1.5px] border-t-[1.5px] px-5 pt-3 pb-[calc(1.25rem+env(safe-area-inset-bottom))] focus:outline-none"
        >
          <div
            class="sheet-handle bg-ink/30 mx-auto mb-3 h-1.5 w-10 rounded-pill"
            aria-hidden="true"
          />
          <h2
            :id="titleId"
            class="mb-3 text-xl"
          >
            {{ title }}
          </h2>
          <slot />
        </div>
      </dialog>
    </Transition>
  </Teleport>
</template>
