import { describe, expect, it } from 'vitest'
import { DEFAULT_PLAN, PLANS, RESULTS, planOf } from './plans'

describe('premium plans', () => {
  it('prices follow the business-model slide', () => {
    expect(PLANS.map((p) => [p.id, p.priceUsd, p.minWalletUsd])).toEqual([
      ['airdrop', 200, 2_000],
      ['perp_rwa', 1_000, 10_000],
    ])
    expect(planOf(DEFAULT_PLAN).priceUsd).toBe(200)
  })

  it('every plan has hunting results whose headline matches its positions', () => {
    for (const p of PLANS) {
      const r = RESULTS[p.id]
      const total = r.protocols.reduce((sum, x) => sum + x.estUsd, 0)
      expect(r.stats[0]).toEqual({ label: 'Est. airdrop value', value: `$${total.toLocaleString('en-US')}` })
      expect(r.summary.length).toBeGreaterThan(0)
    }
  })
})
