import { nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface ModalEntry {
  id: symbol
  panelEl: Ref<HTMLElement | null>
  onClose: () => void
}

// Module-level LIFO stack ensures nested sheets direct Escape and Tab strictly to the topmost open modal.
const modalStack: ModalEntry[] = []
const handledEvents = new WeakSet<Event>()

function isRectPopulated(rect: DOMRect): boolean {
  return rect.width > 0 || rect.height > 0
}

function isEventOutsidePanel(event: MouseEvent, dialogEl: HTMLDialogElement, panelEl: HTMLElement | null): boolean {
  if (!panelEl) return event.target === dialogEl
  const rect = panelEl.getBoundingClientRect()
  if (isRectPopulated(rect)) {
    return (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
  }
  const target = event.target
  return target === dialogEl || !(target instanceof Node && panelEl.contains(target))
}

function closeDialogElement(el: HTMLDialogElement | null): void {
  if (!el) return
  if (typeof el.close === 'function') {
    if (el.open) el.close()
  } else {
    el.removeAttribute('open')
  }
}

export function useModalBehavior(open: Ref<boolean>, onClose: () => void) {
  const dialogEl = ref<HTMLDialogElement | null>(null)
  const panelEl = ref<HTMLElement | null>(null)
  const id = Symbol('modal')

  let active = false
  let attachedDialog: HTMLDialogElement | null = null
  let previouslyFocused: HTMLElement | null = null
  let closeNotified = false
  let pressedOutside = false
  let pressedInside = false
  let suppressNextBackdropClick = false
  let suppressResetTimer: ReturnType<typeof setTimeout> | undefined

  function markSuppressBackdropClick(): void {
    suppressNextBackdropClick = true
    if (suppressResetTimer !== undefined) clearTimeout(suppressResetTimer)
    suppressResetTimer = setTimeout(() => {
      suppressNextBackdropClick = false
      suppressResetTimer = undefined
    }, 0)
  }

  function isTopmost(): boolean {
    return modalStack[modalStack.length - 1]?.id === id
  }

  function requestClose(): void {
    if (closeNotified || !isTopmost()) return
    closeNotified = true
    queueMicrotask(() => {
      closeNotified = false
    })
    onClose()
  }

  function trapTab(event: KeyboardEvent): void {
    const panel = panelEl.value
    const items = Array.from(panel?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
    const first = items[0]
    const last = items[items.length - 1]
    if (!first || !last) {
      event.preventDefault()
      panel?.focus()
    } else if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  function onKeydown(event: KeyboardEvent): void {
    if (!isTopmost() || handledEvents.has(event)) return
    if (event.key === 'Escape') {
      handledEvents.add(event)
      event.preventDefault()
      requestClose()
    } else if (event.key === 'Tab') {
      handledEvents.add(event)
      trapTab(event)
    }
  }

  function onCancel(event: Event): void {
    event.preventDefault()
    if (!active || !isTopmost() || handledEvents.has(event)) return
    handledEvents.add(event)
    requestClose()
  }

  function onPointerDown(event: PointerEvent): void {
    if (!attachedDialog || !isTopmost()) return
    const outside = isEventOutsidePanel(event, attachedDialog, panelEl.value)
    pressedOutside = outside
    pressedInside = !outside
  }

  function onPointerUp(event: PointerEvent): void {
    if (!attachedDialog) return
    const outside = isEventOutsidePanel(event, attachedDialog, panelEl.value)
    const shouldDismiss = pressedOutside && outside && isTopmost()
    const wasInside = pressedInside
    pressedOutside = false
    pressedInside = false
    if (shouldDismiss) {
      markSuppressBackdropClick()
      requestClose()
    } else if (wasInside) {
      markSuppressBackdropClick()
    }
  }

  function onClick(event: MouseEvent): void {
    if (!attachedDialog || !isTopmost()) return
    const suppressed = suppressNextBackdropClick
    suppressNextBackdropClick = false
    if (suppressResetTimer !== undefined) {
      clearTimeout(suppressResetTimer)
      suppressResetTimer = undefined
    }
    if (!suppressed && event.target === attachedDialog) {
      requestClose()
    }
  }

  function bindDialog(el: HTMLDialogElement): void {
    if (attachedDialog === el) return
    unbindDialog()
    attachedDialog = el
    el.addEventListener('cancel', onCancel)
    el.addEventListener('pointerdown', onPointerDown)
    el.addEventListener('pointerup', onPointerUp)
    el.addEventListener('click', onClick)
  }

  function unbindDialog(): void {
    if (!attachedDialog) return
    attachedDialog.removeEventListener('cancel', onCancel)
    attachedDialog.removeEventListener('pointerdown', onPointerDown)
    attachedDialog.removeEventListener('pointerup', onPointerUp)
    attachedDialog.removeEventListener('click', onClick)
    attachedDialog = null
  }

  function openDialog(el: HTMLDialogElement): void {
    if (typeof el.showModal === 'function') {
      if (!el.open) el.showModal()
    } else {
      el.setAttribute('open', '')
    }
  }

  function activate(el: HTMLDialogElement): void {
    if (active) {
      bindDialog(el)
      openDialog(el)
      return
    }
    active = true
    previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    modalStack.push({ id, panelEl, onClose: requestClose })
    document.addEventListener('keydown', onKeydown)
    bindDialog(el)
    openDialog(el)
    void nextTick(() => {
      if (!active) return
      const auto = panelEl.value?.querySelector<HTMLElement>('[autofocus]')
      ;(auto ?? panelEl.value)?.focus()
    })
  }

  function deactivate(closeElementNow: boolean): void {
    if (!active) return
    active = false
    const idx = modalStack.findIndex((entry) => entry.id === id)
    if (idx !== -1) modalStack.splice(idx, 1)
    document.removeEventListener('keydown', onKeydown)
    unbindDialog()
    pressedOutside = false
    pressedInside = false
    suppressNextBackdropClick = false
    if (suppressResetTimer !== undefined) {
      clearTimeout(suppressResetTimer)
      suppressResetTimer = undefined
    }
    if (closeElementNow) closeDialogElement(dialogEl.value)
    previouslyFocused?.focus()
    previouslyFocused = null
  }

  function onAfterLeave(el?: Element): void {
    if (el instanceof HTMLDialogElement) closeDialogElement(el)
    else closeDialogElement(dialogEl.value)
  }

  watch(
    [open, dialogEl],
    ([isOpen, el]) => {
      if (isOpen && el) activate(el)
      else if (!isOpen && active) deactivate(false)
    },
    { immediate: true, flush: 'sync' },
  )

  onBeforeUnmount(() => {
    deactivate(true)
  })

  return { dialogEl, panelEl, onAfterLeave }
}
