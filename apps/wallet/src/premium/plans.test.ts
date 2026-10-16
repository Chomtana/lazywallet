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

  it('perp/RWA volume headline is the sum of its projects, and the plan includes the airdrop programs', () => {
    const [perp, airdrops] = RESULTS.perp_rwa.sections
    const total = perp.projects.reduce((sum, x) => sum + (x.volumeUsd ?? 0), 0)
    expect(RESULTS.perp_rwa.stats[0]).toEqual({ label: 'Volume (24h)', value: `$${total / 1000}K` })
    expect(airdrops).toBe(RESULTS.airdrop.sections[0])
    expect(RESULTS.perp_rwa.stats[2].value).toBe(String(perp.projects.length + airdrops.projects.length))
  })
})
