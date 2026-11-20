<script setup lang="ts">
import type { Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { Link, Plus, QrCode, ReceiptText } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'

// Two-pane home renders its Create button inside TripList so the pane passes `create: false`.
withDefaults(defineProps<{ create?: boolean }>(), { create: true })
defineEmits<{ create: [] }>()

const { t } = useI18n()
const logoUrl = '/logo.svg'

const benefits: { icon: Component; tile: string; key: string }[] = [
  { icon: ReceiptText, tile: 'bg-yellow-soft', key: 'home.benefits.log' },
  { icon: Link, tile: 'bg-sky-soft', key: 'home.benefits.share' },
  { icon: QrCode, tile: 'bg-green-soft', key: 'home.benefits.settle' },
]

const footerLink =
  'flex min-h-11 items-center text-sm font-medium text-ink underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky'
</script>

<template>
  <div class="flex flex-1 flex-col gap-5">
    <div class="flex flex-col items-center gap-3 pt-2 text-center">
      <img
        :src="logoUrl"
        alt=""
        width="84"
        height="84"
      >
      <component
        :is="create ? 'h1' : 'h2'"
        class="text-[20px]"
      >
        {{ t('app.tagline') }}
      </component>
    </div>

    <ul class="flex flex-col gap-3">
      <li
        v-for="item in benefits"
        :key="item.key"
        class="flex items-center gap-3 text-sm text-ink"
      >
        <span
          class="ink-border flex size-[30px] shrink-0 items-center justify-center rounded-[10px]"
          :class="item.tile"
        >
          <component
            :is="item.icon"
            :size="16"
            aria-hidden="true"
          />
        </span>
        {{ t(item.key) }}
      </li>
    </ul>

    <div
      v-if="create"
      class="flex flex-col gap-2"
    >
      <BaseButton
        variant="primary"
        block
        @click="$emit('create')"
      >
        <Plus
          :size="18"
          class="mr-1.5"
          aria-hidden="true"
        />
        {{ t('home.createTrip') }}
      </BaseButton>
      <p class="text-center text-xs text-muted">
        {{ t('home.freeNote') }}
      </p>
    </div>

    <footer class="mt-auto flex items-center justify-between">
      <RouterLink
        to="/demo"
        :class="footerLink"
      >
        {{ t('home.viewSample') }}
      </RouterLink>
      <RouterLink
        to="/join"
        :class="footerLink"
      >
        {{ t('home.haveInvite') }}
      </RouterLink>
    </footer>
  </div>
</template>
