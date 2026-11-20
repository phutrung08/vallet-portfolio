<script setup lang="ts">
import { computed } from 'vue'
import { I18nT, useI18n } from 'vue-i18n'
import type { TripDetail, TripEvent } from '@/entities'
import { iconForKind, sentenceKey } from '@/features/activity/activityKinds'
import { useMoment } from '@/lib/useMoment'

const props = defineProps<{ event: TripEvent; trip: TripDetail }>()

const { t } = useI18n()
const moment = useMoment()
const when = computed(() => moment(props.event.created_at))
const nameOf = (id: string | null) =>
  props.trip.members.find((member) => member.id === id)?.display_name ?? t('activity.someone')
const icon = computed(() => iconForKind(props.event.kind))
</script>

<template>
  <li class="border-ink flex items-start gap-3 border-t-[1.5px] p-3 first:border-t-0">
    <component
      :is="icon"
      :size="20"
      class="mt-0.5 shrink-0"
      aria-hidden="true"
    />
    <div class="min-w-0">
      <I18nT
        :keypath="sentenceKey(event.kind)"
        scope="global"
        tag="p"
        class="break-words"
      >
        <template #actor>
          <strong>{{ nameOf(event.actor_id) }}</strong>
        </template>
        <template #subject>
          {{ nameOf(event.subject_id) }}
        </template>
      </I18nT>
      <p class="text-muted text-xs">
        {{ when.time }} · {{ when.day }}
      </p>
    </div>
  </li>
</template>
