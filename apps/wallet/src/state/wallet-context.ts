import { createContext, useContext } from 'react'
import type { StoredWallet } from '@/types'

export type Status = 'none' | 'locked' | 'unlocked'

export type WalletCtx = {
  status: Status
  wallets: StoredWallet[]
  active: StoredWallet | null
  addWallet(name: string, mnemonic: string, newPassword?: string): Promise<boolean>
  unlock(password: string): Promise<void>
  verifyPassword(password: string): Promise<boolean>
  lock(): void
  setActive(id: string): void
  deleteWallet(id: string): Promise<boolean>
  resetAll(): void
}

export const WalletContext = createContext<WalletCtx | null>(null)

export function useWallet(): WalletCtx {
  const ctx = useContext(WalletContext)
  if (!ctx) throw new Error('useWallet must be used inside <WalletProvider>')
  return ctx
}
