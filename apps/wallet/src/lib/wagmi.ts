import { createConfig, http } from 'wagmi'
import { avalancheFork, ethereumFork } from '@/chain/networks'

export const wagmiConfig = createConfig({
  chains: [ethereumFork, avalancheFork],
  transports: { [ethereumFork.id]: http(), [avalancheFork.id]: http() },
})
