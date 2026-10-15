import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BalanceCard } from './BalanceCard'

describe('BalanceCard', () => {
  it('shows price unknown and leaves the token out of the total', () => {
    render(
      <BalanceCard
        holdings={[
          { network: 'Avalanche', symbol: 'AVAX', amount: 10, usdPrice: 25 },
          { network: 'Avalanche', symbol: 'COQ', amount: 8e6, usdPrice: null },
        ]}
      />,
    )
    expect(screen.getByText('$250.00', { selector: 'p' })).toBeTruthy()
    expect(screen.getByText('price unknown')).toBeTruthy()
  })
})
