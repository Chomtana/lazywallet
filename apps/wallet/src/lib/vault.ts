import { english, generateMnemonic, mnemonicToAccount } from 'viem/accounts'
import { validateMnemonic } from '@scure/bip39'
import type { Address, EncryptedVault, StoredWallet, Vault } from '@/types'
import { uid } from './format'

const ITERATIONS = 210_000

export class WrongPasswordError extends Error {
  constructor() {
    super('Wrong password')
    this.name = 'WrongPasswordError'
  }
}

export function newMnemonic(): string {
  return generateMnemonic(english)
}

export function normalizeMnemonic(input: string): string {
  return input.trim().toLowerCase().split(/\s+/).join(' ')
}

export function isValidMnemonic(m: string): boolean {
  const count = m.split(' ').length
  return (count === 12 || count === 24) && validateMnemonic(m, english)
}

export function addressFromMnemonic(m: string): Address {
  return mnemonicToAccount(m).address
}

export function walletFromMnemonic(name: string, mnemonic: string): StoredWallet {
  return { id: uid(), name: name.trim(), mnemonic, address: addressFromMnemonic(mnemonic) }
}

const toB64 = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes))
const fromB64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0))

async function deriveKey(password: string, salt: Uint8Array<ArrayBuffer>): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, [
    'deriveKey',
  ])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: ITERATIONS, hash: 'SHA-256' },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

export async function encryptVault(vault: Vault, password: string): Promise<EncryptedVault> {
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(password, salt)
  const data = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(JSON.stringify(vault)),
  )
  return { v: 1, salt: toB64(salt), iv: toB64(iv), data: toB64(new Uint8Array(data)) }
}

export async function decryptVault(enc: EncryptedVault, password: string): Promise<Vault> {
  const key = await deriveKey(password, fromB64(enc.salt))
  try {
    const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: fromB64(enc.iv) }, key, fromB64(enc.data))
    return JSON.parse(new TextDecoder().decode(plain)) as Vault
  } catch {
    throw new WrongPasswordError()
  }
}
