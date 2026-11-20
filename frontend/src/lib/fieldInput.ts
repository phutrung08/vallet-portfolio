export type FieldEvent = Event

/**
 * Normalize an input event's value while respecting active IME composition.
 * Returns null while composing so Telex/IME sequences commit before rewriting.
 */
export function applyInput(event: Event, normalise?: (raw: string) => string): string | null {
  if (event instanceof InputEvent && event.isComposing) return null
  const input = event.currentTarget
  if (!(input instanceof HTMLInputElement)) return null
  const next = normalise ? normalise(input.value) : input.value
  if (next !== input.value) input.value = next
  return next
}
