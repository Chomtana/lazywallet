import { createConfig, http } from 'wagmi'
import { defineChain } from 'viem'

export const sandbox = defineChain({
  id: 1,
  name: 'Sandbox (Ethereum fork)',
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: { default: { http: [import.meta.env.VITE_SANDBOX_RPC_URL ?? 'http://localhost:8545'] } },
})

export const wagmiConfig = createConfig({
  chains: [sandbox],
  transports: { [sandbox.id]: http() },
})
