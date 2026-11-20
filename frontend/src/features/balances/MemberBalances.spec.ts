import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { MemberStanding } from '@/entities'
import { balances, standing } from '@/features/balances/balanceFixtures'
import MemberBalances from '@/features/balances/MemberBalances.vue'
import { trip } from '@/features/trips/tripFixtures'
import { createAppI18n } from '@/lib/i18n'

/** Currency output may separate the symbol with a non-breaking space. */
const plain = (text: string | undefined) => text?.replaceAll(' ', ' ')

function mountList(standings: MemberStanding[] = balances.members, hasPayments = false) {
  return mount(MemberBalances, {
    props: { trip, standings, hasPayments },
    global: { plugins: [createAppI18n('en')] },
  })
}

describe('MemberBalances', () => {
  it('shows the captions and one row per member in trip order', () => {
    const view = mountList([...balances.members].reverse())
    expect(view.text()).toContain('Fronted / share owed')
    expect(view.text()).toContain('Difference')
    const rows = view.findAll('li')
    expect(rows).toHaveLength(3)
    expect(rows[0]?.text()).toContain('Alex')
    expect(rows[1]?.text()).toContain('Ben')
    expect(rows[2]?.text()).toContain('Former guest')
  })

  it('shows paid plus contributed over the share, and the signed net', () => {
    const first = mountList().findAll('li')[0]
    expect(plain(first?.text())).toContain('₫500,000 / ₫400,000')
    expect(first?.get('[data-testid="net"]').text()).toContain('+₫100,000')
  })

  it.each([
    [100_000, 'text-green-ink'],
    [-100_000, 'text-danger'],
    [0, 'text-muted'],
  ])('colours a net of %i with %s', (net, expected) => {
    const view = mountList([standing('1', { net })])
    expect(view.get('[data-testid="net"]').classes()).toContain(expected)
  })

  it('fills the bar with what was fronted, capped at the whole share', () => {
    const view = mountList([
      standing('1', { paid: 50_000, share: 200_000 }),
      standing('2', { paid: 300_000, share: 100_000 }),
    ])
    const bars = view.findAll('[role="progressbar"]')
    expect(bars.map((bar) => bar.attributes('aria-valuenow'))).toEqual(['25', '100'])
    expect(bars[0]?.get('div').attributes('style')).toContain('width: 25%')
    expect(plain(bars[1]?.attributes('aria-label'))).toBe('Fronted ₫300,000 of a ₫100,000 share')
  })

  it('flags a member who has left', () => {
    const view = mountList()
    expect(view.findAll('li')[2]?.text()).toContain('left')
    expect(view.findAll('li')[0]?.text()).not.toContain('left')
  })

  it('adds what was sent and received only when payments exist and are not zero', () => {
    const standings = [standing('1', { sent: 0, received: 20_000 }), standing('2', { sent: 20_000 })]
    const without = mountList(standings, false)
    expect(without.text()).not.toContain('sent')
    const view = mountList(standings, true)
    const [first, second] = view.findAll('li')
    expect(first?.text()).toContain('received ₫20,000')
    expect(first?.text()).not.toContain('sent')
    expect(second?.text()).toContain('sent ₫20,000')
    expect(second?.text()).not.toContain('received')
  })
})
