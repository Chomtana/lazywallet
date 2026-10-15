import { getAddress, isAddress } from 'viem'
import type { TrendingToken } from '@/types'

export type BuyOption = { label: string; amount: string; token: string }

const price = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const tinyPrice = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumSignificantDigits: 4 })
const compactUsd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', minimumFractionDigits: 0, maximumFractionDigits: 1 })

// What the card's Buy chips spend, per network: the native coin on Avalanche, USDC on Ethereum.
const BUY_OPTIONS: Record<string, BuyOption[]> = {
  Avalanche: ['0.1', '0.5', '1'].map((amount) => ({ label: `${amount} AVAX`, amount, token: 'AVAX' })),
  Ethereum: ['10', '50', '100'].map((amount) => ({ label: `$${amount} USDC`, amount, token: 'USDC' })),
}

// Minus sign (U+2212) reads better than a hyphen next to numbers.
export function formatChange(pct: number | null): string {
  if (pct === null) return '—'
  const text = Math.abs(pct).toFixed(1)
  return pct > 0 ? `+${text}%` : pct < 0 ? `−${text}%` : `${text}%`
}

export function changeTone(pct: number | null): 'up' | 'down' | 'flat' {
  return pct === null || pct === 0 ? 'flat' : pct > 0 ? 'up' : 'down'
}

export function formatPrice(usd: number | null): string {
  if (usd === null) return '—'
  return usd >= 1 ? price.format(usd) : tinyPrice.format(usd)
}

export function formatCompactUsd(usd: number): string {
  return compactUsd.format(usd)
}

// GeckoTerminal gives some DEXs as ids ("uniswap_v3"); proper names ("LFJ", "Arena DEX") stay as they are.
export function dexName(dex: string): string {
  if (!/^[a-z0-9_-]+$/.test(dex)) return dex
  return dex
    .split(/[_-]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function liquidityLine(t: TrendingToken): string {
  if (!t.dex || t.liquidityUsd <= 0) return 'No DEX market'
  return `${dexName(t.dex)} · ${formatCompactUsd(t.liquidityUsd)} liq`
}

export function initials(symbol: string): string {
  return symbol.replace(/[^a-z0-9]/gi, '').slice(0, 2).toUpperCase() || '?'
}

export function spansNetworks(items: TrendingToken[]): boolean {
  return new Set(items.map((t) => t.network)).size > 1
}

export function buyOptions(network: string): BuyOption[] {
  return BUY_OPTIONS[network] ?? []
}

// Sent as a normal user message; the agent swaps option.token into the token's contract address.
export function buyMessage(t: Pick<TrendingToken, 'symbol' | 'address'>, option: BuyOption): string {
  const address = isAddress(t.address, { strict: false }) ? getAddress(t.address) : t.address
  return `Buy ${option.amount} ${option.token} of ${t.symbol} (${address})`
}
