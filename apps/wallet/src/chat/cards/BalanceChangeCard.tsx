import { formatAmount, formatUsd } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { BalanceChange } from '@/types'

// Minus sign (U+2212) reads better than a hyphen next to numbers.
const sign = (n: number) => (n < 0 ? '−' : '+')

export function BalanceChangeCard({ changes }: { changes: BalanceChange[] }) {
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">Balance change</p>
      <ul className="mt-2 divide-y">
        {changes.map((c) => (
          <li key={`${c.network ?? ''}:${c.symbol}`} className="flex items-center justify-between py-2.5">
            <span>
              <span className="block font-medium">{c.symbol}</span>
              {c.network && <span className="block text-xs text-muted-foreground">{c.network}</span>}
            </span>
            <span className="text-right">
              <span className={cn('block font-mono font-medium', c.delta < 0 ? 'text-destructive' : 'text-primary')}>
                {`${sign(c.delta)}${formatAmount(Math.abs(c.delta))} ${c.symbol}`}
              </span>
              <span className="block text-xs text-muted-foreground">
                {`Now ${formatAmount(c.after)} · ${c.usdPrice === null ? 'price unknown' : `${sign(c.delta)}${formatUsd(Math.abs(c.delta) * c.usdPrice)}`}`}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
