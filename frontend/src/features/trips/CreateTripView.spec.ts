import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import CreateTripView from '@/features/trips/CreateTripView.vue'
import { ApiError, api } from '@/lib/api'
import { createAppI18n } from '@/lib/i18n'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  api: { get: vi.fn(), post: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
const stub = { template: '<div />' }

async function mountForm() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: stub },
      { path: '/trips/new', component: CreateTripView },
      { path: '/trips/:id', component: stub },
    ],
  })
  await router.push('/trips/new')
  await router.isReady()
  const wrapper = mount(CreateTripView, { global: { plugins: [createAppI18n('en'), router] } })
  return { wrapper, router }
}

function input(wrapper: VueWrapper, label: string) {
  const labelEl = wrapper.findAll('label').find((item) => item.text() === label)
  return wrapper.get(`#${CSS.escape(labelEl?.attributes('for') ?? 'missing')}`)
}

async function fill(wrapper: VueWrapper, label: string, value: string) {
  await input(wrapper, label).setValue(value)
}

function button(wrapper: VueWrapper, text: string) {
  const found = wrapper.findAll('button').find((item) => item.text() === text)
  if (!found) throw new Error(`No button ${text}`)
  return found
}

async function addMember(wrapper: VueWrapper, name: string) {
  await fill(wrapper, 'Other members', name)
  await button(wrapper, 'Add').trigger('click')
}

const chipNames = (wrapper: VueWrapper) => wrapper.findAll('ul li span.break-all').map((i) => i.text())

beforeEach(() => {
  get.mockReset().mockResolvedValue({ id: 't1', name: 'x', members: [] })
  post.mockReset().mockResolvedValue({ id: 't1' })
})

describe('CreateTripView validation', () => {
  it('shows required field errors linked via aria-describedby and skips API calls', async () => {
    const { wrapper } = await mountForm()
    await wrapper.get('form').trigger('submit')
    const alerts = wrapper.findAll('[role="alert"]').map((item) => item.text())
    expect(alerts).toEqual(['Enter a trip name', 'Enter a name'])
    const name = input(wrapper, 'Trip name')
    expect(name.attributes('aria-invalid')).toBe('true')
    const described = name.attributes('aria-describedby') ?? ''
    expect(wrapper.get(`#${CSS.escape(described)}`).text()).toBe('Enter a trip name')
    expect(post).not.toHaveBeenCalled()
  })

  it('rejects end dates before start date', async () => {
    const { wrapper } = await mountForm()
    await fill(wrapper, 'Trip name', 'Da Lat')
    await fill(wrapper, 'Your name', 'Alex')
    await fill(wrapper, 'Start date', '2026-11-08')
    await fill(wrapper, 'End date', '2026-11-05')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[role="alert"]').text()).toBe('End date cannot be before the start date')
    expect(post).not.toHaveBeenCalled()
  })

  it('flags creator name collisions with existing member chips', async () => {
    const { wrapper } = await mountForm()
    await fill(wrapper, 'Trip name', 'Da Lat')
    await addMember(wrapper, 'José')
    await fill(wrapper, 'Your name', 'josé'.normalize('NFD'))
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[role="alert"]').text()).toBe('Someone already has this name')
    expect(post).not.toHaveBeenCalled()
  })

  it('clears field error immediately once corrected after a failed submit', async () => {
    const { wrapper } = await mountForm()
    await wrapper.get('form').trigger('submit')
    await fill(wrapper, 'Trip name', 'Da Lat')
    expect(wrapper.findAll('[role="alert"]').map((item) => item.text())).toEqual(['Enter a name'])
  })
})

describe('CreateTripView members', () => {
  it('adds normalised chips via Add button or Enter and removes them cleanly', async () => {
    const { wrapper } = await mountForm()
    await addMember(wrapper, '  Claire   Benson ')
    await fill(wrapper, 'Other members', 'Ben')
    await input(wrapper, 'Other members').trigger('keydown', { key: 'Enter' })
    expect(chipNames(wrapper)).toEqual(['Claire Benson', 'Ben'])
    expect(wrapper.text()).toContain('2/49')
    expect(post).not.toHaveBeenCalled()

    await wrapper.get('button[aria-label="Remove Claire Benson"]').trigger('click')
    expect(chipNames(wrapper)).toEqual(['Ben'])
    expect(wrapper.text()).toContain('1/49')
  })

  it('shows inline error on duplicate names across case and NFD', async () => {
    const { wrapper } = await mountForm()
    await fill(wrapper, 'Your name', 'Alex')
    await addMember(wrapper, 'José')
    for (const duplicate of ['JOSÉ', 'José'.normalize('NFD'), 'alex']) {
      await addMember(wrapper, duplicate)
      expect(wrapper.get('[role="alert"]').text()).toBe('Someone already has this name')
    }
    expect(chipNames(wrapper)).toEqual(['José'])
  })

  it('caps additional members at 49', async () => {
    const { wrapper } = await mountForm()
    for (let index = 0; index < 49; index += 1) await addMember(wrapper, `Person ${index}`)
    expect(wrapper.text()).toContain('49/49')
    await addMember(wrapper, 'One more')
    expect(wrapper.get('[role="alert"]').text()).toBe('Up to 49 other members')
    expect(chipNames(wrapper)).toHaveLength(49)
  })

  it('rejects blank and over-length member names', async () => {
    const { wrapper } = await mountForm()
    await addMember(wrapper, '   ')
    expect(wrapper.get('[role="alert"]').text()).toBe('Enter a name')
    await addMember(wrapper, 'x'.repeat(41))
    expect(wrapper.get('[role="alert"]').text()).toBe('Name can be 40 characters at most')
  })
})

describe('CreateTripView controls', () => {
  it('toggles fund switch and reveals holder notice', async () => {
    const { wrapper } = await mountForm()
    const toggle = wrapper.get('[role="switch"]')
    expect(toggle.attributes('aria-checked')).toBe('false')
    expect(wrapper.text()).not.toContain('You will hold the fund')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-checked')).toBe('true')
    expect(wrapper.text()).toContain('You will hold the fund, and can change that later')
  })

  it('defaults currency to VND and switches to USD', async () => {
    const { wrapper } = await mountForm()
    const radios = wrapper.findAll('input[type="radio"]')
    expect((radios[0]?.element as HTMLInputElement).checked).toBe(true)
    await radios[1]?.setValue(true)
    expect((radios[1]?.element as HTMLInputElement).checked).toBe(true)
  })
})

describe('CreateTripView submit', () => {
  it('submits expected payload and replaces route with new trip', async () => {
    const { wrapper, router } = await mountForm()
    const replace = vi.spyOn(router, 'replace')
    await fill(wrapper, 'Trip name', ' Da  Lat ')
    await fill(wrapper, 'Your name', 'Alex')
    await wrapper.get('[role="switch"]').trigger('click')
    await wrapper.findAll('input[type="radio"]')[1]?.setValue(true)
    await addMember(wrapper, 'Ben')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith('/trips', {
      name: 'Da Lat',
      currency: 'USD',
      uses_fund: true,
      creator_name: 'Alex',
      member_names: ['Ben'],
    })
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/trips/t1'))
    expect(replace).toHaveBeenCalledWith('/trips/t1')
  })

  it('includes configured dates in payload', async () => {
    const { wrapper } = await mountForm()
    await fill(wrapper, 'Trip name', 'Da Lat')
    await fill(wrapper, 'Your name', 'Alex')
    await fill(wrapper, 'Start date', '2026-11-05')
    await fill(wrapper, 'End date', '2026-11-08')
    await wrapper.get('form').trigger('submit')
    expect(post).toHaveBeenCalledWith(
      '/trips',
      expect.objectContaining({ starts_on: '2026-11-05', ends_on: '2026-11-08' }),
    )
  })

  it('disables submit button while request is in flight', async () => {
    let finish: (value: { id: string }) => void = () => {}
    post.mockReturnValue(new Promise((resolve) => (finish = resolve)))
    const { wrapper } = await mountForm()
    await fill(wrapper, 'Trip name', 'Da Lat')
    await fill(wrapper, 'Your name', 'Alex')
    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')
    const submit = wrapper.get('button[type="submit"]')
    expect(submit.text()).toBe('Creating…')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(post).toHaveBeenCalledTimes(1)
    finish({ id: 't1' })
    await flushPromises()
  })

  it('maps 422 field errors without clearing entered data', async () => {
    post.mockRejectedValue(
      new ApiError(422, 'validation_error', 'Invalid request', undefined, ['body.member_names.0']),
    )
    const { wrapper } = await mountForm()
    await fill(wrapper, 'Trip name', 'Da Lat')
    await fill(wrapper, 'Your name', 'Alex')
    await addMember(wrapper, 'Ben')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('This is not valid')
    expect(chipNames(wrapper)).toEqual(['Ben'])
    expect((input(wrapper, 'Trip name').element as HTMLInputElement).value).toBe('Da Lat')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('shows mapped message for general errors and preserves input values', async () => {
    post.mockRejectedValue(new ApiError(0, 'network_error', 'Network error'))
    const { wrapper } = await mountForm()
    await fill(wrapper, 'Trip name', 'Da Lat')
    await fill(wrapper, 'Your name', 'Alex')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('No connection. Please try again.')
    expect((input(wrapper, 'Your name').element as HTMLInputElement).value).toBe('Alex')
  })
})
