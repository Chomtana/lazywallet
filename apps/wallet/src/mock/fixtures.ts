import type { Contact, DappInfo, Holding } from '@/types'

export const HOLDINGS: Holding[] = [
  { symbol: 'ETH', amount: 2.5, usdPrice: 3200 },
  { symbol: 'USDC', amount: 1500, usdPrice: 1 },
  { symbol: 'WBTC', amount: 0.05, usdPrice: 64000 },
]

export const PORTFOLIO_USD = HOLDINGS.reduce((sum, h) => sum + h.amount * (h.usdPrice ?? 0), 0)

// Anvil's default accounts #1 and #2 — they exist on the Sandbox fork.
export const DEFAULT_CONTACTS: Contact[] = [
  { id: 'alice', name: 'Alice', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8' },
  { id: 'bob', name: 'Bob', address: '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC' },
]

// Empty-chat quick starts: the quick actions as full sentences, then the best demos.
export const EXAMPLES = [
  "What's my balance?",
  'What airdrops can I farm?',
  'What are the upcoming token unlocks?',
  'What memecoins are trending?',
  'Swap 1 AVAX to USDC',
  'Farm Avant with 50 USDC',
  'What RWA tokens are hot?',
]

export const UNISWAP: DappInfo = { name: 'Uniswap', url: 'https://app.uniswap.org', icon: '🦄' }
