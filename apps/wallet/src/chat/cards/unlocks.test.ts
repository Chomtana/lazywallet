import { describe, expect, it } from 'vitest'
import type { UnlockItem } from '@/types'
import { dateLabel, detailLine, percentLabel, unlockBuyMessage, unlockBuyOptions, valueLabel } from './unlocks'

const NOW = new Date('2026-10-16T09:00:00Z')
const ZRO: UnlockItem = {
  symbol: 'ZRO', name: 'LayerZero', logo: null, date: '2026-10-20T11:00:00Z', unlockUsd: 53_730_418, unlockAmount: 25_708_334,
  percentOfSupply: 2.5708, allocation: 'Investors, Team', buybackUsd: 352_479.52, burnUsd: null, network: 'Ethereum',
  address: '0x6985884c4392d348587b19cb9eaaf157f13271cd', buyable: true,
}
const AVAX: UnlockItem = { ...ZRO, symbol: 'AVAX', name: 'Avalanche', network: 'Avalanche', address: null, allocation: 'Reserve', buybackUsd: null, burnUsd: 459_773 }

describe('dateLabel', () => {
  it('counts calendar days in UTC, as Tokenomist dates them', () => {
    expect(dateLabel('2026-10-16T23:00:00Z', NOW)).toBe('today · Oct 16')
    expect(dateLabel('2026-10-17T00:00:00Z', NOW)).toBe('tomorrow · Oct 17')
    expect(dateLabel('2026-10-19T00:00:00Z', NOW)).toBe('in 3 days · Oct 19')
    expect(dateLabel('2026-11-08T00:00:00Z', NOW)).toBe('in 23 days · Nov 8')
  })

  it('falls back to the raw text for a bad date', () => {
    expect(dateLabel('soon', NOW)).toBe('soon')
  })
})

describe('formatting', () => {
  it('value and share of supply', () => {
    expect(valueLabel(53_730_418)).toBe('$53.7M')
    expect(valueLabel(null)).toBe('—')
    expect(percentLabel(2.5708)).toBe('2.6% of supply')
    expect(percentLabel(0.04)).toBe('<0.1% of supply')
    expect(percentLabel(null)).toBeNull()
  })

  it('detail line: allocation, then buyback and burn when present', () => {
    expect(detailLine(ZRO)).toBe('Investors, Team · Buyback $352.5K')
    expect(detailLine({ ...ZRO, burnUsd: 63.6e6 })).toBe('Investors, Team · Buyback $352.5K · Burn $63.6M')
    expect(detailLine({ ...ZRO, allocation: null, buybackUsd: null })).toBe('')
  })
})

describe('buy chips', () => {
  it('Ethereum tokens are bought with USDC by contract address', () => {
    const options = unlockBuyOptions(ZRO)
    expect(options.map((o) => o.label)).toEqual(['$10 USDC', '$50 USDC', '$100 USDC'])
    expect(unlockBuyMessage(ZRO, options[1])).toBe('Buy 50 USDC of ZRO (0x6985884C4392D348587B19cb9eAAf157F13271cd)')
  })

  it('Avalanche tokens with an address are bought with AVAX', () => {
    const coq = { ...ZRO, symbol: 'COQ', network: 'Avalanche', address: '0x420fca0121dc28039145009570975747295f2329' as const }
    const options = unlockBuyOptions(coq)
    expect(options.map((o) => o.label)).toEqual(['0.1 AVAX', '0.5 AVAX', '1 AVAX'])
    expect(unlockBuyMessage(coq, options[1])).toBe('Buy 0.5 AVAX of COQ (0x420FcA0121DC28039145009570975747295f2329)')
  })

  it('native AVAX is bought with USDC by symbol', () => {
    const options = unlockBuyOptions(AVAX)
    expect(options.map((o) => o.label)).toEqual(['$10 USDC', '$50 USDC', '$100 USDC'])
    expect(unlockBuyMessage(AVAX, options[1])).toBe('Buy 50 USDC of AVAX')
  })

  it('nothing to buy when not buyable or not on a network', () => {
    expect(unlockBuyOptions({ ...ZRO, buyable: false })).toEqual([])
    expect(unlockBuyOptions({ ...ZRO, network: null, address: null })).toEqual([])
  })
})
