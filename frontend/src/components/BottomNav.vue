<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { Plus, ReceiptText, Scale, Settings, Users } from 'lucide-vue-next'
import NavDragLayer from '@/components/NavDragLayer.vue'
import { useNavDrag } from '@/lib/useNavDrag'
import type { NavLabels } from '@/lib/useNavLabels'
import { useNavPlacement } from '@/lib/useNavPlacement'
import { useTripSource } from '@/lib/tripSource'

const props = withDefaults(
  defineProps<{
    tripId: string
    labels: NavLabels
    shortLabels?: NavLabels
    canAdd?: boolean
  }>(),
  { canAdd: true, shortLabels: undefined },
)

defineEmits<{ add: [] }>()

const source = useTripSource()
const base = computed(() => source.home(props.tripId))
const linkClass =
  'group text-muted flex min-h-11 min-w-11 items-center justify-center desktop:flex-col desktop:gap-0.5 desktop:px-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky'
const iconClass =
  'rounded-pill flex h-9 w-11 items-center justify-center transition-colors motion-reduce:transition-none group-aria-[current=page]:bg-ink group-aria-[current=page]:text-on-accent'
const railLabelClass =
  'text-ink hidden text-center text-[11px] leading-tight font-semibold desktop:block'
const { placement } = useNavPlacement()
// Placement (dock, edge dock, or rail) is driven by styles/nav.css via data attributes.
const navClass = 'bg-cream ink-border shadow-hard rounded-pill px-2.5 py-1'
const { enabled: canDrag, phase, zones, target, moved } = useNavDrag(useTemplateRef('nav'))
</script>

<template>
  <nav
    ref="nav"
    :class="navClass"
    :data-phone="placement.phone"
    :data-wide="placement.wide"
  >
    <ul class="flex items-center gap-3">
      <li>
        <RouterLink
          :to="base"
          :class="linkClass"
          :aria-label="labels.expenses"
        >
          <span :class="iconClass"><ReceiptText aria-hidden="true" /></span>
          <span
            aria-hidden="true"
            :class="railLabelClass"
          >{{ shortLabels?.expenses ?? labels.expenses }}</span>
        </RouterLink>
      </li>
      <li>
        <RouterLink
          :to="`${base}/balances`"
          :class="linkClass"
          :aria-label="labels.balances"
        >
          <span :class="iconClass"><Scale aria-hidden="true" /></span>
          <span
            aria-hidden="true"
            :class="railLabelClass"
          >{{ shortLabels?.balances ?? labels.balances }}</span>
        </RouterLink>
      </li>
      <li
        v-if="!source.readonly && canAdd"
        class="rail:order-first flex flex-col items-center gap-1"
      >
        <button
          type="button"
          :aria-label="labels.add"
          class="ink-border rounded-pill shadow-hard bg-yellow text-on-yellow flex size-12 items-center justify-center transition-[transform,box-shadow] duration-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky motion-reduce:transition-none active:translate-x-[2px] active:translate-y-[3px] active:shadow-none"
          @click="$emit('add')"
        >
          <Plus aria-hidden="true" />
        </button>
        <span
          aria-hidden="true"
          :class="railLabelClass"
        >{{ shortLabels?.add ?? labels.add }}</span>
      </li>
      <li v-if="!source.readonly">
        <RouterLink
          :to="`${base}/members`"
          :class="linkClass"
          :aria-label="labels.members"
        >
          <span :class="iconClass"><Users aria-hidden="true" /></span>
          <span
            aria-hidden="true"
            :class="railLabelClass"
          >{{ shortLabels?.members ?? labels.members }}</span>
        </RouterLink>
      </li>
      <li
        v-if="!source.readonly"
        class="rail:mt-auto"
      >
        <RouterLink
          to="/settings"
          :class="linkClass"
          :aria-label="labels.settings"
        >
          <span :class="iconClass"><Settings aria-hidden="true" /></span>
          <span
            aria-hidden="true"
            :class="railLabelClass"
          >{{ shortLabels?.settings ?? labels.settings }}</span>
        </RouterLink>
      </li>
    </ul>
    <NavDragLayer
      v-if="canDrag"
      :dragging="phase === 'dragging'"
      :zones="zones"
      :target="target"
      :moved="moved"
    />
  </nav>
</template>
