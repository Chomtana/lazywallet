import { describe, expect, it } from 'vitest'
import type { BalanceChange, Holding } from '@/types'
import { groupChanges, groupHoldings } from './balances'

const h = (network: string, symbol: string, amount: number, usdPrice: number | null): Holding => ({ network, symbol, amount, usdPrice })

describe('groupHoldings', () => {
  it('puts the chain with the larger subtotal first and sorts tokens by USD value, unknown prices last', () => {
    const groups = groupHoldings([
      h('Ethereum', 'ETH', 0.01, 3200), // $32
      h('Avalanche', 'COQ', 8e6, null),
      h('Avalanche', 'AVAX', 10, 25), // $250
      h('Ethereum', 'USDC', 5, 1), // $5
      h('Avalanche', 'USDC', 300, 1), // $300
    ])
    expect(groups.map((g) => [g.network, g.subtotal])).toEqual([
      ['Avalanche', 550],
      ['Ethereum', 37],
    ])
    expect(groups[0].items.map((i) => i.symbol)).toEqual(['USDC', 'AVAX', 'COQ'])
    expect(groups[1].items.map((i) => i.symbol)).toEqual(['ETH', 'USDC'])
  })

  it('keeps holdings without a network in one group', () => {
    expect(groupHoldings([h('', 'ETH', 1, 1)]).map((g) => g.network)).toEqual([''])
    expect(groupHoldings([{ symbol: 'ETH', amount: 1, usdPrice: 1 }])[0].network).toBe('')
  })
})

describe('groupChanges', () => {
  const c = (network: string, symbol: string): BalanceChange => ({ network, symbol, before: 0, after: 1, delta: 1, usdPrice: 1 })

  it('groups by chain in first-seen order and keeps the order within a chain', () => {
    const groups = groupChanges([c('Ethereum', 'USDC'), c('Avalanche', 'AVAX'), c('Ethereum', 'ETH')])
    expect(groups.map((g) => [g.network, g.items.map((i) => i.symbol)])).toEqual([
      ['Ethereum', ['USDC', 'ETH']],
      ['Avalanche', ['AVAX']],
    ])
  })
})
