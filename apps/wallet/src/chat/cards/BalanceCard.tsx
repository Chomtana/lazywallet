import { formatAmount, formatUsd } from '@/lib/format'
import type { Holding } from '@/types'

export function BalanceCard({ holdings }: { holdings: Holding[] }) {
  const total = holdings.reduce((sum, h) => sum + h.amount * h.usdPrice, 0)
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">Total balance</p>
      <p className="mt-1 font-mono text-3xl font-semibold">{formatUsd(total)}</p>
      <ul className="mt-4 divide-y">
        {holdings.map((h) => (
          <li key={h.symbol} className="flex items-center justify-between py-2.5">
            <span className="font-medium">{h.symbol}</span>
            <span className="text-right">
              <span className="block font-mono">{formatAmount(h.amount)}</span>
              <span className="block text-xs text-muted-foreground">{formatUsd(h.amount * h.usdPrice)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
