import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { UnlockItem } from '@/types'
import { UnlockListCard } from './UnlockListCard'

const ZRO: UnlockItem = {
  symbol: 'ZRO', name: 'LayerZero', logo: null, date: '2026-10-20T11:00:00Z', unlockUsd: 53_730_418, unlockAmount: 25_708_334,
  percentOfSupply: 2.5708, allocation: 'Investors, Team', buybackUsd: 352_479.52, burnUsd: null, network: 'Ethereum',
  address: '0x6985884c4392d348587b19cb9eaaf157f13271cd', buyable: true,
}
const HYPE: UnlockItem = { ...ZRO, symbol: 'HYPE', name: 'Hyperliquid', network: null, address: null, buyable: false, buybackUsd: null }
const AVAX: UnlockItem = { ...ZRO, symbol: 'AVAX', name: 'Avalanche', network: 'Avalanche', address: null, buybackUsd: null, burnUsd: 459_773 }

afterEach(cleanup)

describe('UnlockListCard', () => {
  it('shows value, share and buyback/burn; Buy only on buyable rows', () => {
    const onBuy = vi.fn()
    render(<UnlockListCard title="Upcoming unlocks" items={[ZRO, HYPE, AVAX]} enabled onBuy={onBuy} />)
    expect(screen.getByText('Upcoming unlocks')).toBeTruthy()
    expect(screen.getAllByText('$53.7M')).toHaveLength(3)
    expect(screen.getByText('Investors, Team · Buyback $352.5K')).toBeTruthy()
    expect(screen.getByText('Investors, Team · Burn $459.8K')).toBeTruthy()
    expect(screen.getByText('Buybacks and burns: last 30 days')).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Ethereum' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Avalanche' })).toBeTruthy()
    const buys = screen.getAllByRole('button', { name: 'Buy' })
    expect(buys).toHaveLength(2) // HYPE isn't buyable
    fireEvent.click(buys[0])
    fireEvent.click(screen.getByRole('button', { name: '$50 USDC' }))
    expect(onBuy).toHaveBeenLastCalledWith('Buy 50 USDC of ZRO (0x6985884C4392D348587B19cb9eAAf157F13271cd)')
    fireEvent.click(buys[1])
    fireEvent.click(screen.getByRole('button', { name: '$100 USDC' }))
    expect(onBuy).toHaveBeenLastCalledWith('Buy 100 USDC of AVAX')
  })

  it('disables Buy when replies are off', () => {
    render(<UnlockListCard title="Upcoming unlocks" items={[ZRO]} enabled={false} onBuy={() => {}} />)
    expect((screen.getByRole('button', { name: 'Buy' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
