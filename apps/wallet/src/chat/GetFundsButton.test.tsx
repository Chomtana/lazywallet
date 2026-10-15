import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FUND_PROMPT, GetFundsButton } from './GetFundsButton'

const requestFunds = vi.fn(async () => '10 ETH')
vi.mock('@/chain/faucet', () => ({ requestFunds: () => requestFunds() }))

const ME = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'

afterEach(() => {
  cleanup()
  requestFunds.mockClear()
})

describe('GetFundsButton', () => {
  it('asks the agent through the chat when it is online, so the new balance card shows', () => {
    const onAsk = vi.fn()
    render(<GetFundsButton address={ME} onFunded={vi.fn()} agentOnline busy={false} onAsk={onAsk} />)
    fireEvent.click(screen.getByRole('button', { name: 'Get funds' }))
    expect(onAsk).toHaveBeenCalledWith(FUND_PROMPT)
    expect(requestFunds).not.toHaveBeenCalled()
  })

  it('calls the faucet directly when the agent is offline', async () => {
    const onAsk = vi.fn()
    const onFunded = vi.fn()
    render(<GetFundsButton address={ME} onFunded={onFunded} agentOnline={false} busy={false} onAsk={onAsk} />)
    fireEvent.click(screen.getByRole('button', { name: 'Get funds' }))
    await vi.waitFor(() => expect(onFunded).toHaveBeenCalled())
    expect(requestFunds).toHaveBeenCalled()
    expect(onAsk).not.toHaveBeenCalled()
  })

  it('shows it is working while the agent is busy', () => {
    render(<GetFundsButton address={ME} onFunded={vi.fn()} agentOnline busy onAsk={vi.fn()} />)
    expect((screen.getByRole('button', { name: 'Adding funds…' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
