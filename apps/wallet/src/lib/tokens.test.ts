import { afterEach, describe, expect, it } from 'vitest'
import type { CustomToken } from '@/types'
import { KEYS } from './storage'
import { savedTokens, saveToken } from './tokens'

const ME = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266'
const OTHER = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'
const COQ: CustomToken = { chainId: 43114, address: '0x420FcA0121DC28039145009570975747295f2329', symbol: 'COQ', decimals: 18 }
const PEPE: CustomToken = { chainId: 1, address: '0x6982508145454Ce325dDbE47a25d4ec3d2311933', symbol: 'PEPE', decimals: 18 }

afterEach(() => localStorage.clear())

describe('custom token store', () => {
  it('adds tokens per wallet, keyed by lowercase address', () => {
    expect(saveToken(ME, COQ)).toBe(true)
    expect(saveToken(ME.toLowerCase(), PEPE)).toBe(true)
    expect(savedTokens(ME)).toEqual([COQ, PEPE])
    expect(Object.keys(JSON.parse(localStorage.getItem(KEYS.tokens)!))).toEqual([ME.toLowerCase()])
  })

  it('dedupes by chain and address, ignoring case', () => {
    saveToken(ME, COQ)
    saveToken(ME, { ...COQ, address: COQ.address.toLowerCase() as CustomToken['address'], symbol: 'coq' })
    expect(savedTokens(ME)).toEqual([COQ])
    saveToken(ME, { ...COQ, chainId: 1 })
    expect(savedTokens(ME)).toHaveLength(2)
  })

  it('keeps wallets apart', () => {
    saveToken(ME, COQ)
    expect(savedTokens(OTHER)).toEqual([])
  })

  it('survives corrupt or unexpected JSON', () => {
    localStorage.setItem(KEYS.tokens, '{not json')
    expect(savedTokens(ME)).toEqual([])
    localStorage.setItem(KEYS.tokens, '[1,2]')
    expect(savedTokens(ME)).toEqual([])
    localStorage.setItem(KEYS.tokens, JSON.stringify({ [ME.toLowerCase()]: 'nope' }))
    expect(savedTokens(ME)).toEqual([])
    expect(saveToken(ME, COQ)).toBe(true)
    expect(savedTokens(ME)).toEqual([COQ])
  })
})
