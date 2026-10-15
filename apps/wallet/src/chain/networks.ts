import { defineChain } from 'viem'

export const ethereumFork = defineChain({
  id: 1,
  name: 'Ethereum',
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: { default: { http: [import.meta.env.VITE_SANDBOX_RPC_URL ?? 'http://localhost:8545'] } },
})

export const avalancheFork = defineChain({
  id: 43114,
  name: 'Avalanche',
  nativeCurrency: { name: 'Avalanche', symbol: 'AVAX', decimals: 18 },
  rpcUrls: { default: { http: [import.meta.env.VITE_SANDBOX_AVAX_RPC_URL ?? 'http://localhost:8546'] } },
})

export const sandboxChains = [ethereumFork, avalancheFork] as const

export function chainById(id = 1) {
  return sandboxChains.find((c) => c.id === id)
}

export function networkName(id = 1): string {
  return chainById(id)?.name ?? `Chain ${id}`
}
