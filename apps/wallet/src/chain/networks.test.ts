import { describe, expect, it } from 'vitest'
import { chainById, networkName } from './networks'

describe('networks', () => {
  it('names sandbox chains and defaults to Ethereum', () => {
    expect(networkName(43114)).toBe('Avalanche')
    expect(networkName(1)).toBe('Ethereum')
    expect(networkName()).toBe('Ethereum')
    expect(networkName(10)).toBe('Chain 10')
    expect(chainById(43114)?.nativeCurrency.symbol).toBe('AVAX')
  })
})
