import { describe, expect, it } from 'vitest'
import { formatAmount, formatUsd, hostOf, shortAddress, txHash } from './format'

describe('format', () => {
  it('shortens addresses', () => {
    expect(shortAddress('0x70997970C51812dc3A010C7d01b50e0d17dc79C8')).toBe('0x7099…79C8')
    expect(shortAddress('0x1234')).toBe('0x1234')
  })

  it('formats USD', () => {
    expect(formatUsd(1234.5)).toBe('$1,234.50')
  })

  it('formats amounts to 6 significant digits without trailing zeros', () => {
    expect(formatAmount(0.031171875)).toBe('0.0311719')
    expect(formatAmount(1500)).toBe('1500')
    expect(formatAmount(2.5)).toBe('2.5')
  })

  it('extracts host, falling back to input', () => {
    expect(hostOf('https://app.uniswap.org/swap')).toBe('app.uniswap.org')
    expect(hostOf('not a url')).toBe('not a url')
  })

  it('makes 32-byte hex hashes', () => {
    expect(txHash()).toMatch(/^0x[0-9a-f]{64}$/)
  })
})
