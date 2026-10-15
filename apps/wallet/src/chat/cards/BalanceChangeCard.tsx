import { ChainIcon } from '@/components/ChainIcon'
import { TokenLogo } from '@/components/TokenLogo'
import { groupChanges } from '@/lib/balances'
import { formatAmount, formatUsd } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { BalanceChange } from '@/types'

// Minus sign (U+2212) reads better than a hyphen next to numbers.
const sign = (n: number) => (n < 0 ? '−' : '+')

export function BalanceChangeCard({ changes }: { changes: BalanceChange[] }) {
  return (
    <div className="rounded-2xl border bg-card p-3">
      <p className="text-xs text-muted-foreground">Balance change</p>
      {groupChanges(changes).map((g) => (
        <section key={g.network} className="mt-2">
          {g.network && (
            <p className="flex items-center gap-1.5 border-b pb-1 text-xs text-muted-foreground">
              <ChainIcon network={g.network} size={14} />
              {g.network}
            </p>
          )}
          <ul>
            {g.items.map((c) => (
              <li key={c.symbol} className="flex h-10 items-center gap-2.5">
                <TokenLogo src={c.logo} symbol={c.symbol} className="size-7" />
                <span className="min-w-0 flex-1 truncate text-sm font-semibold">{c.symbol}</span>
                <span className="shrink-0 text-right leading-tight">
                  <span className={cn('block font-mono text-sm font-medium', c.delta < 0 ? 'text-destructive' : 'text-primary')}>
                    {`${sign(c.delta)}${formatAmount(Math.abs(c.delta))} ${c.symbol}`}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {`Now ${formatAmount(c.after)} · ${c.usdPrice === null ? 'price unknown' : `${sign(c.delta)}${formatUsd(Math.abs(c.delta) * c.usdPrice)}`}`}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
