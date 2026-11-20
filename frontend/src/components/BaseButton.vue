<script setup lang="ts">
type Variant = 'primary' | 'success' | 'dark' | 'outline' | 'danger' | 'danger-outline'

withDefaults(
  defineProps<{
    variant?: Variant
    block?: boolean
    disabled?: boolean
    type?: 'button' | 'submit'
  }>(),
  { variant: 'primary', block: false, disabled: false, type: 'button' },
)

const variantClass: Record<Variant, string> = {
  primary: 'bg-yellow text-on-yellow',
  success: 'bg-green text-on-green',
  dark: 'bg-ink text-on-accent',
  outline: 'bg-surface text-ink',
  danger: 'bg-danger text-on-accent',
  'danger-outline': 'bg-surface text-danger border-danger',
}
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    class="ink-border rounded-pill shadow-hard font-body inline-flex min-h-11 items-center justify-center px-5 font-medium transition-[transform,box-shadow] duration-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky motion-reduce:transition-none enabled:active:translate-x-[2px] enabled:active:translate-y-[3px] enabled:active:shadow-none disabled:cursor-not-allowed disabled:bg-sand disabled:text-ink/75 disabled:shadow-none"
    :class="[variantClass[variant], block && 'w-full']"
  >
    <slot />
  </button>
</template>
