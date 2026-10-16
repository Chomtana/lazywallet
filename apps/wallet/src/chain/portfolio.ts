import { erc20Abi, formatUnits, parseAbi, type Address } from 'viem'
import { publicClientFor } from './client'

// Below this total the chat offers a one-tap "Get funds" button.
export const FUNDS_THRESHOLD_USD = 1000

export type Reading = { raw: bigint; decimals: number; usdPrice: number }

const FEED_DECIMALS = 8 // Chainlink */USD feeds

export function feedPrice(answer: bigint): number | null {
  return answer > 0n ? Number(formatUnits(answer, FEED_DECIMALS)) : null
}

// USD value of the readings; null if any read failed (we never guess).
export function totalUsd(readings: (Reading | null)[]): number | null {
  let sum = 0
  for (const r of readings) {
    if (!r) return null
    sum += Number(formatUnits(r.raw, r.decimals)) * r.usdPrice
  }
  return sum
}

export function needsFunds(usd: number | null): boolean {
  return usd !== null && usd < FUNDS_THRESHOLD_USD
}

// Same tokens and feeds as agent/lazyagent/tokens.py.
const CHAINS = [
  {
    chainId: 1,
    feed: '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419', // ETH/USD
    stables: ['0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7'], // USDC, USDT
  },
  {
    chainId: 43114,
    feed: '0x0A77230d17318075983913bC2145DB16C7366156', // AVAX/USD
    stables: ['0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E', '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7'], // USDC, USDT
  },
] as const

const feedAbi = parseAbi([
  'function latestRoundData() view returns (uint80, int256 answer, uint256, uint256, uint80)',
])

async function readChain(owner: Address, { chainId, feed, stables }: (typeof CHAINS)[number]): Promise<Reading[]> {
  const client = publicClientFor(chainId)
  const [native, round, ...stableRaw] = await Promise.all([
    client.getBalance({ address: owner }),
    client.readContract({ address: feed, abi: feedAbi, functionName: 'latestRoundData' }),
    ...stables.map((address) => client.readContract({ address, abi: erc20Abi, functionName: 'balanceOf', args: [owner] })),
  ])
  const price = feedPrice(round[1])
  if (price === null) throw new Error(`Bad price feed on chain ${chainId}`)
  return [{ raw: native, decimals: 18, usdPrice: price }, ...stableRaw.map((raw) => ({ raw, decimals: 6, usdPrice: 1 }))]
}

// Total USD across both forks (native + USDC/USDT); null when any chain can't be read.
export async function readPortfolioUsd(owner: Address): Promise<number | null> {
  try {
    return totalUsd((await Promise.all(CHAINS.map((c) => readChain(owner, c)))).flat())
  } catch {
    return null
  }
}
