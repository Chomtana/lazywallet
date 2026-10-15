import type { Contact, DappInfo, Holding } from '@/types'

export const HOLDINGS: Holding[] = [
  { symbol: 'ETH', amount: 2.5, usdPrice: 3200 },
  { symbol: 'USDC', amount: 1500, usdPrice: 1 },
  { symbol: 'WBTC', amount: 0.05, usdPrice: 64000 },
]

export const PORTFOLIO_USD = HOLDINGS.reduce((sum, h) => sum + h.amount * h.usdPrice, 0)

// Anvil's default accounts #1 and #2 — they exist on the Sandbox fork.
export const DEFAULT_CONTACTS: Contact[] = [
  { id: 'alice', name: 'Alice', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8' },
  { id: 'bob', name: 'Bob', address: '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC' },
]

export const EXAMPLES = [
  "What's my balance?",
  'Send 0.1 ETH to Alice',
  'Swap 100 USDC to ETH',
  'Alert me if ETH drops below 3000',
  'Buy ETH every Monday with 50 USDC',
  'If ETH < 3000, swap 500 USDC to ETH',
]

export const UNISWAP: DappInfo = { name: 'Uniswap', url: 'https://app.uniswap.org', icon: '🦄' }
