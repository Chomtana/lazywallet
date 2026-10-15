import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AirdropItem } from '@/types'
import { AirdropCard } from './AirdropCard'

const THEO: AirdropItem = {
  id: 'theo-thusd', name: 'Theo thUSD Points', category: 'rwa', networks: ['Ethereum'], status: 'live',
  action: 'Stake thUSD into sthUSD', tvlUsd: 132e6, farm: 'Theo', buy: null,
}
const RE: AirdropItem = {
  id: 're', name: 'Re Points Season 2', category: 'rwa', networks: ['Ethereum', 'Avalanche'], status: 'live',
  action: 'Hold reUSD', tvlUsd: null, farm: null, buy: { symbol: 'reUSD', address: '0x5086bf358635B81D8C47C66d1C8b9E567Db70c72' },
}
const AVANT: AirdropItem = {
  id: 'avant', name: 'Avant Season 1 points', category: 'other', networks: ['Avalanche'], status: 'live',
  action: 'Stake avUSD into savUSD', tvlUsd: 126e6, farm: 'Avant', buy: null,
}
const SUZAKU: AirdropItem = {
  id: 'suzaku-s2', name: 'Suzaku Points Season 2', category: 'other', networks: ['Avalanche'], status: 'unverified',
  action: 'Deposit into Suzaku restaking vaults', tvlUsd: 1e6, farm: null, buy: null,
}

describe('AirdropCard', () => {
  afterEach(cleanup)

  it('Farm reveals amount chips and sends the farm message, one farm per chain', () => {
    const onSend = vi.fn()
    render(<AirdropCard title="Airdrops" items={[THEO, RE, AVANT, SUZAKU]} enabled onSend={onSend} />)
    expect(screen.getByText('Airdrops')).toBeTruthy()
    expect(screen.getByText('may have ended')).toBeTruthy()
    expect(screen.queryByText('$50')).toBeNull()
    const [theoFarm, avantFarm] = screen.getAllByText('Farm')
    fireEvent.click(theoFarm)
    fireEvent.click(screen.getByText('$50'))
    expect(onSend).toHaveBeenLastCalledWith('Farm Theo with 50 USDC')
    expect(screen.queryByText('$50')).toBeNull()
    fireEvent.click(avantFarm)
    fireEvent.click(screen.getByText('$100'))
    expect(onSend).toHaveBeenLastCalledWith('Farm Avant with 100 USDC')
  })

  it('Buy sends the token with its contract address; rows without either get no button', () => {
    const onSend = vi.fn()
    render(<AirdropCard title="Airdrops" items={[RE, SUZAKU]} enabled onSend={onSend} />)
    expect(screen.getAllByRole('button')).toHaveLength(1)
    fireEvent.click(screen.getByText('Buy reUSD'))
    fireEvent.click(screen.getByText('$10'))
    expect(onSend).toHaveBeenCalledWith('Buy 10 USDC of reUSD (0x5086bf358635B81D8C47C66d1C8b9E567Db70c72)')
  })

  it('shows chain icons instead of a category badge or network text', () => {
    render(<AirdropCard title="Airdrops" items={[RE]} enabled onSend={vi.fn()} />)
    expect(screen.getByRole('img', { name: 'Ethereum' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Avalanche' })).toBeTruthy()
    expect(screen.queryByText('RWA')).toBeNull()
    expect(screen.queryByText(/Ethereum ·/)).toBeNull()
    expect(screen.queryByText(/sandbox/i)).toBeNull()
  })

  it('buttons are disabled while the agent is busy or offline', () => {
    render(<AirdropCard title="Airdrops" items={[THEO]} enabled={false} onSend={vi.fn()} />)
    expect((screen.getByText('Farm') as HTMLButtonElement).disabled).toBe(true)
  })
})
