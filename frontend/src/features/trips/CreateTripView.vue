<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import BaseButton from '@/components/BaseButton.vue'
import TextField from '@/components/TextField.vue'
import CurrencyToggle from '@/features/trips/CurrencyToggle.vue'
import FundSwitch from '@/features/trips/FundSwitch.vue'
import MemberChips from '@/features/trips/MemberChips.vue'
import type { ErrorKey } from '@/features/trips/tripFormRules'
import { useCreateTripForm } from '@/features/trips/useCreateTripForm'
import { errorMessageKey } from '@/lib/errors'

const { t } = useI18n()
const { form, errors, submitError, pending, submit } = useCreateTripForm()

function message(key: ErrorKey | undefined): string | undefined {
  return key && t(`createTrip.errors.${key}`)
}
</script>

<template>
  <main class="col-center flex min-h-dvh flex-col p-4">
    <RouterLink
      to="/"
      class="-ml-2 flex min-h-11 items-center gap-1 self-start px-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
    >
      <ChevronLeft
        :size="18"
        aria-hidden="true"
      />
      {{ t('trip.back') }}
    </RouterLink>
    <h1 class="mb-4 text-2xl">
      {{ t('createTrip.title') }}
    </h1>

    <form
      class="flex flex-1 flex-col gap-5"
      novalidate
      @submit.prevent="submit"
    >
      <TextField
        v-model="form.name"
        :label="t('createTrip.name')"
        :placeholder="t('createTrip.namePlaceholder')"
        :error="message(errors.name)"
      />
      <div class="grid grid-cols-2 items-start gap-3">
        <TextField
          v-model="form.startsOn"
          type="date"
          :label="t('createTrip.startsOn')"
        />
        <TextField
          v-model="form.endsOn"
          type="date"
          :label="t('createTrip.endsOn')"
          :error="message(errors.dates)"
        />
      </div>
      <FundSwitch v-model="form.usesFund" />
      <CurrencyToggle v-model="form.currency" />
      <TextField
        v-model="form.creatorName"
        :label="t('createTrip.yourName')"
        autocomplete="given-name"
        :error="message(errors.creatorName)"
      />
      <MemberChips
        v-model="form.memberNames"
        :creator-name="form.creatorName"
        :error="errors.members"
      />

      <div class="bg-cream sticky bottom-0 -mx-4 mt-auto flex flex-col gap-2 px-4 pt-3 pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <p
          v-if="submitError"
          role="alert"
          class="text-danger text-sm"
        >
          {{ t(errorMessageKey(submitError)) }}
        </p>
        <BaseButton
          type="submit"
          block
          :disabled="pending"
        >
          {{ pending ? t('createTrip.submitting') : t('createTrip.submit') }}
        </BaseButton>
      </div>
    </form>
  </main>
</template>
