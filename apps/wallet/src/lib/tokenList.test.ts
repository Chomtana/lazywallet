import { describe, expect, it } from 'vitest'
import type { TrendingToken } from '@/types'
import { buyMessage, buyOptions, changeTone, dexName, formatChange, formatCompactUsd, formatPrice, initials, liquidityLine, spansNetworks } from './tokenList'

const COQ: TrendingToken = {
  symbol: 'COQ',
  name: 'COQINU',
  network: 'Avalanche',
  address: '0x420fca0121dc28039145009570975747295f2329',
  priceUsd: 1.2164e-7,
  change24h: -5.1,
  liquidityUsd: 623_823.6,
  dex: 'LFJ',
  buyable: true,
  note: null,
  image: null,
}
const ONDO: TrendingToken = { ...COQ, symbol: 'ONDO', name: 'Ondo', network: 'Ethereum', address: '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3' }

describe('tokenList', () => {
  it('formats 24h change with a sign, and a dash when unknown', () => {
    expect(formatChange(2.345)).toBe('+2.3%')
    expect(formatChange(-5.1)).toBe('−5.1%')
    expect(formatChange(0)).toBe('0.0%')
    expect(formatChange(null)).toBe('—')
  })

  it('tones change up, down or flat', () => {
    expect([changeTone(1), changeTone(-0.2), changeTone(0), changeTone(null)]).toEqual(['up', 'down', 'flat', 'flat'])
  })

  it('formats prices, keeping tiny ones readable', () => {
    expect(formatPrice(4151.7951)).toBe('$4,151.80')
    expect(formatPrice(0.43)).toBe('$0.43')
    expect(formatPrice(1.2164e-7)).toBe('$0.0000001216')
    expect(formatPrice(null)).toBe('—')
  })

  it('formats liquidity as compact USD', () => {
    expect(formatCompactUsd(623_823.6)).toBe('$623.8K')
    expect(formatCompactUsd(1_765_680)).toBe('$1.8M')
    expect(formatCompactUsd(950)).toBe('$950')
  })

  it('names DEXs readably, leaving proper names alone', () => {
    expect(dexName('uniswap_v3')).toBe('Uniswap V3')
    expect(dexName('blackhole-v3')).toBe('Blackhole V3')
    expect(dexName('LFJ')).toBe('LFJ')
    expect(dexName('Arena DEX')).toBe('Arena DEX')
  })

  it('describes liquidity, or the lack of a market', () => {
    expect(liquidityLine(COQ)).toBe('LFJ · $623.8K liq')
    expect(liquidityLine({ ...COQ, dex: '', liquidityUsd: 0 })).toBe('No DEX market')
  })

  it('takes initials from the symbol', () => {
    expect(initials('XAUt0')).toBe('XA')
    expect(initials('$WIF')).toBe('WI')
    expect(initials('A')).toBe('A')
    expect(initials('???')).toBe('?')
  })

  it('shows network tags only when the list spans networks', () => {
    expect(spansNetworks([COQ, COQ])).toBe(false)
    expect(spansNetworks([COQ, ONDO])).toBe(true)
  })

  it('offers AVAX amounts on Avalanche and USDC amounts on Ethereum', () => {
    expect(buyOptions('Avalanche').map((o) => o.label)).toEqual(['0.1 AVAX', '0.5 AVAX', '1 AVAX'])
    expect(buyOptions('Ethereum').map((o) => o.label)).toEqual(['$10 USDC', '$50 USDC', '$100 USDC'])
    expect(buyOptions('Solana')).toEqual([])
  })

  it('writes the buy message with the checksummed contract address', () => {
    const [, half] = buyOptions('Avalanche')
    expect(buyMessage(COQ, half)).toBe('Buy 0.5 AVAX of COQ (0x420FcA0121DC28039145009570975747295f2329)')
    const [, fifty] = buyOptions('Ethereum')
    expect(buyMessage(ONDO, fifty)).toBe('Buy 50 USDC of ONDO (0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3)')
  })
})
