import { formatCompactUsd } from '@/lib/tokenList'
import type { AirdropItem } from '@/types'

export const AMOUNTS_USDC = [10, 50, 100] as const

const STATUS: Record<AirdropItem['status'], string> = { live: 'live', unverified: 'may have ended', claim_pending: 'claim not open yet' }

export function statusLabel(status: AirdropItem['status']): string {
  return STATUS[status] ?? status
}

export function tvlLabel(tvlUsd: number | null): string {
  return tvlUsd === null ? 'TVL unknown' : `TVL ${formatCompactUsd(tvlUsd)}`
}

/** What a Farm chip sends — the agent maps it to propose_deposit. */
export function farmReply(farm: string, usdc: number): string {
  return `Farm ${farm} with ${usdc} USDC`
}

/** What a Buy chip sends — the full address so the agent swaps the exact token. */
export function buyReply(buy: NonNullable<AirdropItem['buy']>, usdc: number): string {
  return `Buy ${usdc} USDC of ${buy.symbol} (${buy.address})`
}
