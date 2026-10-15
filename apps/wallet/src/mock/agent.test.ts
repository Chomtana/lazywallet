import { describe, expect, it } from 'vitest'
import type { AgentReply, Contact } from '@/types'
import { respond, simulateTrigger } from './agent'
import { HOLDINGS } from './fixtures'

const contacts: Contact[] = [{ id: '1', name: 'Alice', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8' }]
const ctx = { contacts, holdings: HOLDINGS }

function confirmOf(reply: AgentReply) {
  const m = reply.messages.find((x) => x.kind === 'confirm')
  if (!m || m.kind !== 'confirm') throw new Error('expected a confirm card')
  return m.tx
}
const textOf = (reply: AgentReply) =>
  reply.messages.flatMap((m) => (m.role === 'assistant' && m.kind === 'text' ? [m.text] : [])).join(' ')
const hasConfirm = (reply: AgentReply) => reply.messages.some((m) => m.kind === 'confirm')
const row = (tx: { rows: { label: string; value: string }[] }, label: string) =>
  tx.rows.find((r) => r.label === label)?.value ?? ''

describe('respond', () => {
  it('shows balances', () => {
    const r = respond("What's my balance?", ctx)
    expect(r.messages.some((m) => m.kind === 'balance')).toBe(true)
  })

  it('sends to a contact, tolerating voice punctuation and capitals', () => {
    const tx = confirmOf(respond('Send 0.1 ETH to Alice.', ctx))
    expect(tx.title).toBe('Send 0.1 ETH')
    expect(row(tx, 'To')).toContain('Alice')
  })

  it('sends to a raw address and shows it checksummed', () => {
    const tx = confirmOf(respond('send 1 usdc to 0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc', ctx))
    expect(row(tx, 'To')).toBe('0x3C44…93BC')
  })

  it('refuses unknown recipients without a confirm card', () => {
    const r = respond('send 0.1 eth to charlie', ctx)
    expect(hasConfirm(r)).toBe(false)
    expect(textOf(r)).toMatch(/address book/i)
  })

  it('refuses amounts above the balance or zero', () => {
    expect(hasConfirm(respond('send 10 eth to alice', ctx))).toBe(false)
    expect(textOf(respond('send 10 eth to alice', ctx))).toMatch(/only have 2.5 ETH/)
    expect(hasConfirm(respond('send 0 eth to alice', ctx))).toBe(false)
  })

  it('quotes swaps', () => {
    const tx = confirmOf(respond('Swap 100 USDC to ETH', ctx))
    expect(row(tx, 'You receive')).toContain('0.0311562 ETH')
    expect(row(tx, 'Route')).toBe('Uniswap v3')
  })

  it('refuses unsupported swap tokens', () => {
    const r = respond('swap 1 doge to eth', ctx)
    expect(hasConfirm(r)).toBe(false)
    expect(textOf(r)).toMatch(/ETH, USDC and WBTC/)
  })

  it('explains bridging is not available', () => {
    expect(textOf(respond('Bridge 0.05 ETH to Base', ctx))).toMatch(/coming soon/i)
  })

  it('creates a price alert from a spoken amount with separators', () => {
    const r = respond('Alert me if ETH drops below $3,000.', ctx)
    expect(r.newTask?.kind).toBe('alert')
    expect(r.newTask?.description).toContain('$3,000')
  })

  it('creates a conditional order that can be simulated', () => {
    const r = respond('If ETH < 3000, swap 500 USDC to ETH', ctx)
    expect(r.newTask?.kind).toBe('conditional')
    expect(r.newTask?.trigger?.title).toBe('Swap 500 USDC → ETH')
    const fired = simulateTrigger(r.newTask!)
    expect(confirmOf(fired).title).toBe('Swap 500 USDC → ETH')
  })

  it('refuses conditional orders with zero or more than the balance', () => {
    for (const input of ['If ETH < 3000, swap 0 USDC to ETH', 'If ETH < 3000, swap 99999 USDC to ETH']) {
      const r = respond(input, ctx)
      expect(r.newTask).toBeUndefined()
      expect(hasConfirm(r)).toBe(false)
    }
  })

  it('falls back with examples', () => {
    expect(textOf(respond('make me rich', ctx))).toMatch(/Try:/)
  })
})
