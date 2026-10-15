import type { CustomToken } from '@/types'
import { KEYS, readJSON, writeJSON } from './storage'

// lw.tokens: { [walletAddressLowercase]: CustomToken[] } — non-secret, add-only.
type Store = Record<string, CustomToken[]>

function load(): Store {
  const s = readJSON<unknown>(KEYS.tokens, {})
  return s && typeof s === 'object' && !Array.isArray(s) ? (s as Store) : {}
}

export function savedTokens(wallet: string): CustomToken[] {
  const list = load()[wallet.toLowerCase()]
  return Array.isArray(list) ? list : []
}

export function saveToken(wallet: string, token: CustomToken): boolean {
  const store = load()
  const key = wallet.toLowerCase()
  const list = savedTokens(key)
  const same = (t: CustomToken) => t.chainId === token.chainId && t.address.toLowerCase() === token.address.toLowerCase()
  if (list.some(same)) return true
  return writeJSON(KEYS.tokens, { ...store, [key]: [...list, token] })
}
