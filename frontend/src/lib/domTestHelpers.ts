import { flushPromises } from '@vue/test-utils'

/** Active teleported modal dialog element in document.body. */
export const dialog = () => document.body.querySelector<HTMLElement>('dialog[open], [role="dialog"]')

/** First button whose trimmed text matches ``label``. */
export const button = (root: ParentNode | null | undefined, label: string) =>
  [...(root?.querySelectorAll('button') ?? [])].find((item) => item.textContent?.trim() === label)

export async function click(element: Element | undefined | null): Promise<void> {
  element?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
}

export async function submitSheet(): Promise<void> {
  dialog()?.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }))
  await flushPromises()
}

export async function typeInto(input: HTMLInputElement | null | undefined, value: string): Promise<void> {
  if (!input) throw new Error('input missing')
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

export const buttonContaining = (root: ParentNode | null | undefined, part: string) =>
  [...(root?.querySelectorAll('button') ?? [])].find((item) => item.textContent?.includes(part))
