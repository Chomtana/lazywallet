import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BalanceChangeCard } from './BalanceChangeCard'

describe('BalanceChangeCard', () => {
  it('shows only the given tokens with signed diffs and new balances', () => {
    render(
      <BalanceChangeCard
        changes={[
          { network: 'Ethereum', symbol: 'ETH', before: 10, after: 9, delta: -1, usdPrice: 3200 },
          { network: 'Ethereum', symbol: 'USDC', before: 5000, after: 7358, delta: 2358, usdPrice: 1 },
        ]}
      />,
    )
    expect(screen.getByText('Balance change')).toBeTruthy()
    expect(screen.getByText('−1 ETH')).toBeTruthy()
    expect(screen.getByText('+2358 USDC')).toBeTruthy()
    expect(screen.getByText('Now 9 · −$3,200.00')).toBeTruthy()
    expect(screen.getByText('Now 7358 · +$2,358.00')).toBeTruthy()
    expect(screen.queryByText(/DAI/)).toBeNull()
  })

  it('says price unknown instead of $0 for a custom token without a price', () => {
    render(<BalanceChangeCard changes={[{ network: 'Avalanche', symbol: 'COQ', before: 0, after: 8e6, delta: 8e6, usdPrice: null }]} />)
    expect(screen.getByText('Now 8000000 · price unknown')).toBeTruthy()
  })
})
