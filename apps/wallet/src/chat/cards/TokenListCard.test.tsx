import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { TrendingToken } from '@/types'
import { TokenListCard } from './TokenListCard'

const COQ: TrendingToken = {
  symbol: 'COQ',
  name: 'COQINU',
  network: 'Avalanche',
  address: '0x420fca0121dc28039145009570975747295f2329',
  priceUsd: 1.2e-7,
  change24h: -5.1,
  liquidityUsd: 623_823.6,
  dex: 'LFJ',
  buyable: true,
  note: null,
  image: null,
}
const NXRA: TrendingToken = { ...COQ, symbol: 'NXRA', name: 'Nexera', address: '0x644192291cc835a93d6330b24ea5f5fedd0eef9e', buyable: false }

afterEach(cleanup) // no vitest globals, so Testing Library doesn't clean up on its own

describe('TokenListCard', () => {
  it('reveals amount chips on Buy and sends the buy message', () => {
    const onBuy = vi.fn()
    render(<TokenListCard title="Trending memecoins" items={[COQ, NXRA]} enabled onBuy={onBuy} />)
    expect(screen.getAllByRole('button', { name: 'Buy' })).toHaveLength(1) // NXRA isn't buyable
    expect(screen.queryByText('0.5 AVAX')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Buy' }))
    fireEvent.click(screen.getByRole('button', { name: '0.5 AVAX' }))
    expect(onBuy).toHaveBeenCalledWith('Buy 0.5 AVAX of COQ (0x420FcA0121DC28039145009570975747295f2329)')
    expect(screen.queryByRole('img', { name: 'Avalanche' })).toBeNull() // one network: no tags
  })

  it('tags networks when the list spans them, and disables Buy when replies are off', () => {
    render(<TokenListCard title="Hot RWA tokens" items={[COQ, { ...COQ, network: 'Ethereum', symbol: 'ONDO' }]} enabled={false} onBuy={() => {}} />)
    expect(screen.getByRole('img', { name: 'Ethereum' })).toBeTruthy()
    for (const b of screen.getAllByRole('button', { name: 'Buy' })) expect((b as HTMLButtonElement).disabled).toBe(true)
  })
})
