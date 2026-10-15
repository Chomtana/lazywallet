import { afterEach, describe, expect, it, vi } from 'vitest'
import { requestFunds } from './faucet'

const ADDRESS = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'

afterEach(() => vi.unstubAllGlobals())

describe('requestFunds', () => {
  it('returns the faucet summary', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ summary: '10 ETH' }), { status: 200 })))
    expect(await requestFunds(ADDRESS)).toBe('10 ETH')
  })

  it('explains when the sandbox is not running', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(requestFunds(ADDRESS)).rejects.toThrow('pnpm dev:sandbox')
  })

  it('surfaces faucet errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Sandbox chain error: x' }), { status: 502 })))
    await expect(requestFunds(ADDRESS)).rejects.toThrow('Sandbox chain error: x')
  })
})
