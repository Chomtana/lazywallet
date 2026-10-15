// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { KEYS } from '@/lib/storage'
import { useWallet } from './wallet-context'
import { WalletProvider } from './WalletProvider'

const PHRASE_A = 'test test test test test test test test test test test junk'
const PHRASE_B = 'legal winner thank year wave sausage worth useful legal winner thank yellow'
const wrapper = ({ children }: { children: ReactNode }) => <WalletProvider>{children}</WalletProvider>

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

async function createVault() {
  const first = renderHook(() => useWallet(), { wrapper })
  await act(() => first.result.current.addWallet('A', PHRASE_A, 'password1'))
  first.unmount()
  return localStorage.getItem(KEYS.vault)
}

describe('WalletProvider', () => {
  it('refuses to create a new vault over an existing locked one', async () => {
    const stored = await createVault()
    const { result } = renderHook(() => useWallet(), { wrapper })
    expect(result.current.status).toBe('locked')
    let ok = true
    await act(async () => {
      ok = await result.current.addWallet('B', PHRASE_B, 'password2')
    })
    expect(ok).toBe(false)
    expect(localStorage.getItem(KEYS.vault)).toBe(stored)
  })

  it('locks when another tab changes the vault', async () => {
    const { result } = renderHook(() => useWallet(), { wrapper })
    await act(() => result.current.addWallet('A', PHRASE_A, 'password1'))
    expect(result.current.status).toBe('unlocked')
    act(() => {
      window.dispatchEvent(new StorageEvent('storage', { key: KEYS.vault }))
    })
    expect(result.current.status).toBe('locked')
  })

  it('reports a failed delete when storage is unavailable', async () => {
    const { result } = renderHook(() => useWallet(), { wrapper })
    await act(() => result.current.addWallet('A', PHRASE_A, 'password1'))
    await act(() => result.current.addWallet('B', PHRASE_B))
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    let ok = true
    await act(async () => {
      ok = await result.current.deleteWallet(result.current.wallets[0].id)
    })
    expect(ok).toBe(false)
    expect(result.current.wallets).toHaveLength(2)
  })
})
