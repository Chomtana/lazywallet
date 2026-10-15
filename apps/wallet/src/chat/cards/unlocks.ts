import { buyMessage, buyOptions, formatCompactUsd, type BuyOption } from '@/lib/tokenList'
import type { UnlockItem } from '@/types'

const DAY_MS = 86_400_000
// Tokenomist dates unlocks in UTC (most at 00:00Z), so the day count and the date are UTC too.
const shortDate = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

function utcDay(d: Date): number {
  return Math.floor(d.getTime() / DAY_MS)
}

/** "today · Oct 16", "tomorrow · Oct 17", "in 3 days · Oct 19". */
export function dateLabel(iso: string, now: Date = new Date()): string {
  const when = new Date(iso)
  if (Number.isNaN(when.getTime())) return iso
  const days = utcDay(when) - utcDay(now)
  const rel = days <= 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days} days`
  return `${rel} · ${shortDate.format(when)}`
}

export function valueLabel(usd: number | null): string {
  return usd === null ? '—' : formatCompactUsd(usd)
}

export function percentLabel(pct: number | null): string | null {
  if (pct === null) return null
  return pct < 0.1 ? '<0.1% of supply' : `${pct.toFixed(1)}% of supply`
}

/** "Investors, Team · Buyback $352.5K · Burn $63.6M" — each part only when present. */
export function detailLine(u: UnlockItem): string {
  const parts = [u.allocation]
  if (u.buybackUsd) parts.push(`Buyback ${formatCompactUsd(u.buybackUsd)}`)
  if (u.burnUsd) parts.push(`Burn ${formatCompactUsd(u.burnUsd)}`)
  return parts.filter(Boolean).join(' · ')
}

/** Same chips as the token list: AVAX on Avalanche, USDC on Ethereum — except native AVAX, bought with USDC. */
export function unlockBuyOptions(u: UnlockItem): BuyOption[] {
  if (!u.buyable || !u.network) return []
  return u.address ? buyOptions(u.network) : buyOptions('Ethereum')
}

export function unlockBuyMessage(u: UnlockItem, option: BuyOption): string {
  return u.address ? buyMessage({ symbol: u.symbol, address: u.address }, option) : `Buy ${option.amount} ${option.token} of ${u.symbol}`
}
