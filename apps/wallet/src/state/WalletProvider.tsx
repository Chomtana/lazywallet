import { useEffect, useState, type ReactNode } from 'react'
import { KEYS, readJSON, removeKey, writeJSON } from '@/lib/storage'
import { decryptVault, encryptVault, walletFromMnemonic } from '@/lib/vault'
import type { EncryptedVault, Vault } from '@/types'
import { WalletContext, type Status, type WalletCtx } from './wallet-context'

const loadEncrypted = () => readJSON<EncryptedVault | null>(KEYS.vault, null)

export function WalletProvider({ children }: { children: ReactNode }) {
  const [vault, setVault] = useState<Vault | null>(null)
  const [password, setPassword] = useState<string | null>(null)
  const [hasStored, setHasStored] = useState(() => loadEncrypted() !== null)
  const [activeId, setActiveId] = useState<string | null>(() => readJSON<string | null>(KEYS.active, null))

  const status: Status = vault ? 'unlocked' : hasStored ? 'locked' : 'none'
  const wallets = vault?.wallets ?? []
  const active = wallets.find((w) => w.id === activeId) ?? wallets[0] ?? null

  // Another tab changed the vault: drop our in-memory copy so we never write over its changes.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key !== null && e.key !== KEYS.vault) return
      setVault(null)
      setPassword(null)
      setHasStored(loadEncrypted() !== null)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  function setActive(id: string) {
    setActiveId(id)
    writeJSON(KEYS.active, id)
  }

  async function persist(next: Vault, pw: string): Promise<boolean> {
    const ok = writeJSON(KEYS.vault, await encryptVault(next, pw))
    if (ok) {
      setVault(next)
      setPassword(pw)
      setHasStored(true)
    }
    return ok
  }

  async function addWallet(name: string, mnemonic: string, newPassword?: string) {
    // Without an unlocked session this creates a fresh vault, which must never replace an existing one.
    if (!password && loadEncrypted() !== null) return false
    const pw = password ?? newPassword
    if (!pw) throw new Error('A password is required to create the vault')
    const wallet = walletFromMnemonic(name, mnemonic)
    const ok = await persist({ wallets: [...wallets, wallet] }, pw)
    if (ok) setActive(wallet.id)
    return ok
  }

  async function unlock(pw: string) {
    const enc = loadEncrypted()
    if (!enc) throw new Error('No vault on this device')
    setVault(await decryptVault(enc, pw))
    setPassword(pw)
  }

  async function verifyPassword(pw: string) {
    const enc = loadEncrypted()
    if (!enc) return false
    try {
      await decryptVault(enc, pw)
      return true
    } catch {
      return false
    }
  }

  function lock() {
    setVault(null)
    setPassword(null)
  }

  function resetAll() {
    removeKey(KEYS.vault)
    removeKey(KEYS.active)
    setVault(null)
    setPassword(null)
    setHasStored(false)
    setActiveId(null)
  }

  async function deleteWallet(id: string) {
    const rest = wallets.filter((w) => w.id !== id)
    if (rest.length === 0) {
      resetAll()
      return true
    }
    return password ? persist({ wallets: rest }, password) : false
  }

  const value: WalletCtx = {
    status,
    wallets,
    active,
    addWallet,
    unlock,
    verifyPassword,
    lock,
    setActive,
    deleteWallet,
    resetAll,
  }
  return <WalletContext value={value}>{children}</WalletContext>
}
