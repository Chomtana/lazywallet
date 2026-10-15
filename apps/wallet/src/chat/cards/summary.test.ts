import { describe, expect, it } from 'vitest'
import type { TxSummary } from '@/types'
import { stepsHeading, summaryFooter, usdLabel } from './summary'

const swap: TxSummary = {
  kind: 'swap',
  network: 'Avalanche',
  pay: { symbol: 'AVAX', amount: '1', usd: 25, logo: null },
  receive: { symbol: 'COQ', amount: '≈ 8000000', usd: null, logo: null, note: null },
  via: 'KyberSwap via LFJ',
  fee: '≈ $0.02',
  warning: null,
}

describe('confirm card summary', () => {
  it('footer names the venue for a swap and the program for a farm', () => {
    expect(summaryFooter(swap)).toBe('via KyberSwap via LFJ · fee ≈ $0.02')
    const farm: TxSummary = {
      ...swap,
      kind: 'farm',
      via: undefined,
      swap: { symbol: 'avUSD', amount: '≈ 50', via: 'KyberSwap via Pharaoh', logo: null },
      program: 'Avant points program',
    }
    expect(summaryFooter(farm)).toBe('Avant points program · fee ≈ $0.02')
  })

  it('formats USD and leaves unknown prices blank', () => {
    expect(usdLabel(1234.5)).toBe('$1,234.50')
    expect(usdLabel(null)).toBeNull()
  })

  it('counts the steps', () => {
    expect(stepsHeading(1)).toBe('1 step')
    expect(stepsHeading(4)).toBe('4 steps — one tap runs them in order')
  })
})
