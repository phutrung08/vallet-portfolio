<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import type { TripSummary } from '@/entities'
import TripCard from '@/features/trips/TripCard.vue'

defineProps<{ trips: TripSummary[]; today: string; split?: boolean; selectedId?: string | null }>()
defineEmits<{ create: []; select: [trip: TripSummary] }>()

const { t } = useI18n()
</script>

<template>
  <div class="flex flex-1 flex-col gap-4">
    <h1 class="text-[20px]">
      {{ t('home.yourTrips') }}
    </h1>
    <p
      v-if="trips.length === 0"
      class="text-muted text-sm"
    >
      {{ t('home.noTrips') }}
    </p>
    <ul class="flex flex-col gap-3">
      <li
        v-for="trip in trips"
        :key="trip.id"
      >
        <TripCard
          :trip="trip"
          :today="today"
          :split="split"
          :selected="trip.id === selectedId"
          @select="$emit('select', trip)"
        />
      </li>
    </ul>
    <BaseButton
      variant="primary"
      block
      class="mt-auto"
      @click="$emit('create')"
    >
      <Plus
        :size="18"
        class="mr-1.5"
        aria-hidden="true"
      />
      {{ t('home.createTrip') }}
    </BaseButton>
  </div>
</template>
