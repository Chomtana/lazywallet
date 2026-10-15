// @vitest-environment node
import { describe, expect, it } from 'vitest'
import {
  WrongPasswordError,
  decryptVault,
  encryptVault,
  isValidMnemonic,
  newMnemonic,
  normalizeMnemonic,
  walletFromMnemonic,
} from './vault'

const TEST_MNEMONIC = 'test test test test test test test test test test test junk'

describe('mnemonics', () => {
  it('generates a valid 12-word mnemonic', () => {
    const m = newMnemonic()
    expect(m.split(' ')).toHaveLength(12)
    expect(isValidMnemonic(m)).toBe(true)
  })

  it('normalizes spacing, newlines and case', () => {
    expect(normalizeMnemonic('  Test test\n\ntest  TEST ')).toBe('test test test test')
  })

  it('rejects wrong word count and misspelled words', () => {
    expect(isValidMnemonic('test test test test test test test test test test test')).toBe(false)
    expect(isValidMnemonic('test test test test test test test test test test test junkk')).toBe(false)
  })

  it('derives the standard first account', () => {
    const w = walletFromMnemonic('  Main ', TEST_MNEMONIC)
    expect(w.name).toBe('Main')
    expect(w.address).toBe('0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266')
    expect(w.id).toBeTruthy()
  })
})

describe('vault encryption', () => {
  const vault = { wallets: [walletFromMnemonic('Main', TEST_MNEMONIC)] }

  it('round-trips with the right password', async () => {
    const enc = await encryptVault(vault, 'hunter22')
    expect(await decryptVault(enc, 'hunter22')).toEqual(vault)
  })

  it('throws WrongPasswordError with the wrong password', async () => {
    const enc = await encryptVault(vault, 'hunter22')
    await expect(decryptVault(enc, 'nope')).rejects.toBeInstanceOf(WrongPasswordError)
  })

  it('does not contain the plaintext mnemonic', async () => {
    const enc = await encryptVault(vault, 'hunter22')
    expect(JSON.stringify(enc)).not.toContain('junk')
  })

  it('uses a fresh salt and iv each time', async () => {
    const a = await encryptVault(vault, 'hunter22')
    const b = await encryptVault(vault, 'hunter22')
    expect(a.salt).not.toBe(b.salt)
    expect(a.iv).not.toBe(b.iv)
  })
})
