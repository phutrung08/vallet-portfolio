<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import AppWordmark from '@/components/AppWordmark.vue'
import BaseButton from '@/components/BaseButton.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import JoinInviteCard from '@/features/join/JoinInviteCard.vue'
import JoinPasteForm from '@/features/join/JoinPasteForm.vue'
import JoinPicker from '@/features/join/JoinPicker.vue'
import { useJoin } from '@/features/join/useJoin'
import { errorMessageKey } from '@/lib/errors'

const { t } = useI18n()
const join = useJoin()
const rejected = ref(false)
const canSubmit = computed(() => {
  const { creating, memberId } = join.choice
  return !join.submitting.value && !join.preview.value?.trip.locked && (creating || memberId !== null)
})

function onPaste(raw: string): void {
  rejected.value = !join.start(raw)
}
</script>

<template>
  <main class="col-center flex min-h-dvh flex-col gap-5 p-4">
    <header>
      <AppWordmark size="md" />
    </header>

    <JoinPasteForm
      v-if="join.phase.value === 'paste'"
      :rejected="rejected"
      @submit="onPaste"
    />
    <div
      v-else-if="join.phase.value === 'loading'"
      aria-busy="true"
    >
      <span class="sr-only">{{ t('common.loading') }}</span>
      <div class="card-ink bg-sand h-36 animate-pulse motion-reduce:animate-none" />
    </div>
    <div
      v-else-if="join.phase.value === 'gone'"
      role="alert"
      class="card-ink bg-surface flex flex-col items-start gap-3 p-4"
    >
      <h1 class="text-xl">
        {{ t('join.goneTitle') }}
      </h1>
      <p>{{ t('join.goneBody') }}</p>
      <RouterLink
        to="/"
        class="inline-flex min-h-11 items-center font-medium text-ink underline"
      >
        {{ t('notFound.home') }}
      </RouterLink>
    </div>
    <ErrorNotice
      v-else-if="join.phase.value === 'failed'"
      :message="t(errorMessageKey(join.failure.value))"
      @retry="join.load"
    />
    <template v-else-if="join.preview.value">
      <JoinInviteCard :preview="join.preview.value" />
      <div
        v-if="join.preview.value.me !== null"
        class="flex flex-col gap-3"
      >
        <p>{{ t('join.alreadyJoined') }}</p>
        <BaseButton
          variant="dark"
          block
          @click="join.openTrip"
        >
          {{ t('join.openTrip') }}
        </BaseButton>
      </div>
      <form
        v-else
        class="flex flex-1 flex-col gap-5"
        novalidate
        @submit.prevent="join.submit"
      >
        <JoinPicker
          v-model:member-id="join.choice.memberId"
          v-model:creating="join.choice.creating"
          v-model:new-name="join.choice.newName"
          :members="join.preview.value.members"
          :name-error-key="join.nameErrorKey.value"
        />
        <div class="mt-auto flex flex-col gap-2">
          <p
            v-if="join.preview.value.trip.locked"
            role="alert"
            class="text-danger text-sm"
          >
            {{ t('join.locked') }}
          </p>
          <p
            v-else-if="join.submitError.value"
            role="alert"
            class="text-danger text-sm"
          >
            {{ t(errorMessageKey(join.submitError.value)) }}
          </p>
          <BaseButton
            type="submit"
            variant="dark"
            block
            :disabled="!canSubmit"
          >
            {{ t('join.submit') }}
          </BaseButton>
          <p class="text-muted text-center text-xs">
            {{ t('join.caption') }}
          </p>
        </div>
      </form>
    </template>
  </main>
</template>
