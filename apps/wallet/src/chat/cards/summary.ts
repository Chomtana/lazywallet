import { formatUsd } from '@/lib/format'
import type { TxSummary } from '@/types'

export function summaryFooter(s: TxSummary): string {
  const lead = s.kind === 'farm' ? (s.program ?? 'Farm') : `via ${s.via}`
  return `${lead} · fee ${s.fee}`
}

export function usdLabel(usd: number | null): string | null {
  return usd === null ? null : formatUsd(usd)
}

export function stepsHeading(n: number): string {
  return n === 1 ? '1 step' : `${n} steps — one tap runs them in order`
}
