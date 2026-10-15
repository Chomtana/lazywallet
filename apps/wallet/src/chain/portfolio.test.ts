import { describe, expect, it } from 'vitest'
import { feedPrice, needsFunds, totalUsd } from './portfolio'

const usdc = (n: bigint) => ({ raw: n * 10n ** 6n, decimals: 6, usdPrice: 1 })
const eth = (wei: bigint, usdPrice: number) => ({ raw: wei, decimals: 18, usdPrice })

describe('feedPrice', () => {
  it('reads a Chainlink answer with 8 decimals', () => {
    expect(feedPrice(320_012_345_678n)).toBeCloseTo(3200.12345678)
  })

  it('rejects a non-positive answer', () => {
    expect(feedPrice(0n)).toBeNull()
    expect(feedPrice(-1n)).toBeNull()
  })
})

describe('totalUsd', () => {
  it('is 0 for an empty wallet', () => {
    expect(totalUsd([usdc(0n), eth(0n, 3000)])).toBe(0)
  })

  it('sums tokens and native coins at their prices', () => {
    expect(totalUsd([usdc(500n), eth(10n ** 17n, 3000)])).toBeCloseTo(800)
  })

  it('is null when any read failed', () => {
    expect(totalUsd([usdc(500n), null])).toBeNull()
  })
})

describe('needsFunds', () => {
  it('offers funds at $0', () => expect(needsFunds(0)).toBe(true))
  it('offers funds just below $1,000', () => expect(needsFunds(999.99)).toBe(true))
  it('stops offering at exactly $1,000', () => expect(needsFunds(1000)).toBe(false))
  it('stops offering above $1,000', () => expect(needsFunds(25_000)).toBe(false))
  it('hides the offer when the balance is unknown', () => expect(needsFunds(null)).toBe(false))
})
