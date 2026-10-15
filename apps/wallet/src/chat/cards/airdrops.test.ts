import { describe, expect, it } from 'vitest'
import { AMOUNTS_USDC, buyReply, farmReply, statusLabel, tvlLabel } from './airdrops'

describe('airdrop card helpers', () => {
  it('labels statuses in plain words', () => {
    expect(statusLabel('live')).toBe('live')
    expect(statusLabel('unverified')).toBe('may have ended')
    expect(statusLabel('claim_pending')).toBe('claim not open yet')
  })

  it('shows TVL compactly, or unknown', () => {
    expect(tvlLabel(132_161_995.8)).toBe('TVL $132.2M')
    expect(tvlLabel(1_037_041)).toBe('TVL $1M')
    expect(tvlLabel(null)).toBe('TVL unknown')
  })

  it('builds the chat messages the chips send', () => {
    expect(AMOUNTS_USDC).toEqual([10, 50, 100])
    expect(farmReply('Theo', 50)).toBe('Farm Theo with 50 USDC')
    expect(farmReply('Avant', 10)).toBe('Farm Avant with 10 USDC')
    expect(buyReply({ symbol: 'reUSD', address: '0x5086bf358635B81D8C47C66d1C8b9E567Db70c72' }, 10)).toBe(
      'Buy 10 USDC of reUSD (0x5086bf358635B81D8C47C66d1C8b9E567Db70c72)',
    )
  })
})
