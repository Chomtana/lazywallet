import { createPublicClient, createWalletClient, http, type PublicClient } from 'viem'
import { mnemonicToAccount } from 'viem/accounts'
import { chainById } from './networks'
import type { TxDeps } from './executeTx'

const readers = new Map<number, PublicClient>()

// A cached read-only client for one Sandbox chain.
export function publicClientFor(chainId = 1): PublicClient {
  const cached = readers.get(chainId)
  if (cached) return cached
  const chain = chainById(chainId)
  if (!chain) throw new Error(`Unknown network (chain ${chainId}).`)
  const client = createPublicClient({ chain, transport: http(chain.rpcUrls.default.http[0]) })
  readers.set(chainId, client)
  return client
}

export function txDepsFor(mnemonic: string): TxDeps {
  const account = mnemonicToAccount(mnemonic)
  const perChain = new Map<number, TxDeps>()

  // One wallet + reader client per Sandbox chain, created on first use.
  function depsFor(chainId = 1): TxDeps {
    const cached = perChain.get(chainId)
    if (cached) return cached
    const chain = chainById(chainId)
    if (!chain) throw new Error(`Unknown network (chain ${chainId}).`)
    const transport = http(chain.rpcUrls.default.http[0])
    const wallet = createWalletClient({ account, chain, transport })
    const reader = createPublicClient({ chain, transport })
    const deps: TxDeps = {
      send: (req) => wallet.sendTransaction({ to: req.to, value: BigInt(req.value), data: req.data }),
      wait: async (hash) => (await reader.waitForTransactionReceipt({ hash })).status,
    }
    perChain.set(chainId, deps)
    return deps
  }

  return {
    send: async (req) => depsFor(req.chainId).send(req),
    wait: (hash, chainId) => depsFor(chainId).wait(hash),
  }
}
