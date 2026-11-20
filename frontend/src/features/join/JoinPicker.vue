<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { UserPlus } from 'lucide-vue-next'
import MemberPicker from '@/components/MemberPicker.vue'
import TextField from '@/components/TextField.vue'
import type { PreviewMember } from '@/entities'

const memberId = defineModel<string | null>('memberId', { required: true })
const creating = defineModel<boolean>('creating', { required: true })
const newName = defineModel<string>('newName', { required: true })
const props = defineProps<{ members: readonly PreviewMember[]; nameErrorKey: string | null }>()

const { t } = useI18n()
const options = computed(() =>
  props.members.map((member) => ({
    id: member.id,
    name: member.display_name,
    hint: member.joined ? t('join.alreadyIn') : undefined,
  })),
)

// Selecting an existing member clears new-person entry and vice versa.
const picked = computed({
  get: () => memberId.value,
  set: (id) => {
    memberId.value = id
    creating.value = false
  },
})

function startNew(): void {
  creating.value = true
  memberId.value = null
}
</script>

<template>
  <section class="flex flex-col gap-3">
    <h2 class="text-lg">
      {{ t('join.whoAreYou') }}
    </h2>
    <MemberPicker
      v-model="picked"
      :label="t('join.whoAreYou')"
      :options="options"
    />
    <button
      type="button"
      :aria-pressed="creating"
      class="rounded-card text-ink flex min-h-12 w-full items-center justify-center gap-2 border-[1.5px] border-dashed border-edge font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky aria-pressed:bg-green-soft"
      @click="startNew"
    >
      <UserPlus
        :size="18"
        aria-hidden="true"
      />
      {{ t('join.newPerson') }}
    </button>
    <TextField
      v-if="creating"
      v-model="newName"
      :label="t('join.yourName')"
      autocomplete="given-name"
      :error="nameErrorKey ? t(nameErrorKey) : undefined"
    />
  </section>
</template>
