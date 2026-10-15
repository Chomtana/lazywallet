import { ChainIcon } from '@/components/ChainIcon'
import { TokenLogo } from '@/components/TokenLogo'
import { groupHoldings } from '@/lib/balances'
import { formatAmount, formatUsd } from '@/lib/format'
import type { Holding } from '@/types'

export function BalanceCard({ holdings }: { holdings: Holding[] }) {
  const total = holdings.reduce((sum, h) => sum + (h.usdPrice === null ? 0 : h.amount * h.usdPrice), 0)
  return (
    <div className="rounded-2xl border bg-card p-3">
      <p className="text-xs text-muted-foreground">Total balance</p>
      <p className="font-mono text-2xl font-semibold">{formatUsd(total)}</p>
      {groupHoldings(holdings).map((g) => (
        <section key={g.network} className="mt-3">
          {g.network && (
            <div className="flex items-center justify-between border-b pb-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <ChainIcon network={g.network} size={14} />
                {g.network}
              </span>
              <span className="font-mono">{formatUsd(g.subtotal)}</span>
            </div>
          )}
          <ul>
            {g.items.map((h) => (
              <li key={h.symbol} className="flex h-10 items-center gap-2.5">
                <TokenLogo src={h.logo} symbol={h.symbol} className="size-7" />
                <span className="min-w-0 flex-1 leading-tight">
                  <span className="block truncate text-sm font-semibold">{h.symbol}</span>
                  <span className="block font-mono text-xs text-muted-foreground">{formatAmount(h.amount)}</span>
                </span>
                <span className="shrink-0 text-right font-mono text-sm">
                  {h.usdPrice === null ? <span className="text-xs text-muted-foreground">price unknown</span> : formatUsd(h.amount * h.usdPrice)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
