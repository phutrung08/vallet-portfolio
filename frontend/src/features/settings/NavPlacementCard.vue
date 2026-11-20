<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/BaseCard.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import NavPlacementPreview from '@/features/settings/NavPlacementPreview.vue'
import { useMediaQuery } from '@/lib/useMediaQuery'
import {
  WIDE_PLACEMENTS,
  useNavPlacement,
  type PhonePlacement,
  type WidePlacement,
} from '@/lib/useNavPlacement'

const { t } = useI18n()
const { placement, setPhone, setWide } = useNavPlacement()

// Matches --breakpoint-phone-lg (25rem) and --breakpoint-rail (37.5rem) in tokens.css.
const isPhoneLarge = useMediaQuery('(min-width: 25rem)')
const isWide = useMediaQuery('(min-width: 37.5rem)')

const phone = computed<PhonePlacement>({ get: () => placement.phone, set: setPhone })
const wide = computed<WidePlacement>({ get: () => placement.wide, set: setWide })

function options<T extends string>(group: 'phone' | 'wide', values: readonly T[]) {
  return values.map((value) => ({ value, label: t(`settings.navPlacement.${group}.${value}`) }))
}
const bottomOptions = computed(() =>
  options<PhonePlacement>('phone', ['bottom-left', 'bottom-center', 'bottom-right']),
)
const edgeOptions = computed(() => options<PhonePlacement>('phone', ['edge-left', 'edge-right']))
const wideOptions = computed(() => options<WidePlacement>('wide', WIDE_PLACEMENTS))
</script>

<template>
  <BaseCard
    as="section"
    class="flex flex-col gap-3 p-4"
  >
    <h2 class="text-xl">
      {{ t('settings.navPlacement.title') }}
    </h2>

    <p
      v-if="!isPhoneLarge"
      class="text-sm"
    >
      {{ t('settings.navPlacement.small') }}
    </p>

    <template v-else-if="!isWide">
      <h3 class="text-base">
        {{ t('settings.navPlacement.phoneTitle') }}
      </h3>
      <NavPlacementPreview
        kind="phone"
        :value="phone"
      />
      <SegmentedControl
        v-model="phone"
        :label="t('settings.navPlacement.bottomGroup')"
        :options="bottomOptions"
      />
      <SegmentedControl
        v-model="phone"
        :label="t('settings.navPlacement.edgeGroup')"
        :options="edgeOptions"
      />
    </template>

    <template v-else>
      <h3 class="text-base">
        {{ t('settings.navPlacement.wideTitle') }}
      </h3>
      <NavPlacementPreview
        kind="wide"
        :value="wide"
      />
      <SegmentedControl
        v-model="wide"
        :label="t('settings.navPlacement.wideTitle')"
        :options="wideOptions"
      />
    </template>

    <template v-if="isPhoneLarge">
      <p class="text-sm">
        {{ t('settings.navPlacement.dragTip') }}
      </p>
      <p class="text-muted text-xs">
        {{ t('settings.navPlacement.otherSize') }}
      </p>
    </template>
  </BaseCard>
</template>
