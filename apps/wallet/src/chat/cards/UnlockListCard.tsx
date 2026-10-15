import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ChainIcon } from '@/components/ChainIcon'
import { TokenLogo } from '@/components/TokenLogo'
import { cn } from '@/lib/utils'
import type { UnlockItem } from '@/types'
import { dateLabel, detailLine, percentLabel, unlockBuyMessage, unlockBuyOptions, valueLabel } from './unlocks'

type Props = { title: string; items: UnlockItem[]; enabled: boolean; onBuy: (text: string) => void }

export function UnlockListCard({ title, items, enabled, onBuy }: Props) {
  const [open, setOpen] = useState<string | null>(null) // key of the row whose Buy chips are showing
  const hasPeriodData = items.some((u) => u.buybackUsd || u.burnUsd)
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="font-semibold">{title}</p>
      <ul className="mt-2 divide-y">
        {items.map((u) => {
          const key = `${u.symbol}:${u.date}`
          const options = unlockBuyOptions(u)
          const detail = detailLine(u)
          const pct = percentLabel(u.percentOfSupply)
          return (
            <li key={key} className="py-2.5">
              <div className={cn('flex items-center gap-3', options.length === 0 && 'opacity-50')}>
                <TokenLogo src={u.logo} symbol={u.symbol} />
                <div className="min-w-0 flex-1">
                  <p className="flex items-baseline gap-1.5">
                    <span className="font-semibold">{u.symbol}</span>
                    <span className="truncate text-sm text-muted-foreground">{u.name}</span>
                  </p>
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="truncate">{dateLabel(u.date)}</span>
                    {u.network && <ChainIcon network={u.network} size={14} />}
                  </p>
                  {detail && <p className="truncate text-xs text-muted-foreground">{detail}</p>}
                </div>
                <div className="shrink-0 text-right">
                  <span className="block font-mono text-sm">{valueLabel(u.unlockUsd)}</span>
                  {pct && <span className="block font-mono text-xs text-muted-foreground">{pct}</span>}
                </div>
                {options.length > 0 && (
                  <Button className="h-9 px-5 font-semibold" disabled={!enabled} onClick={() => setOpen(open === key ? null : key)}>
                    Buy
                  </Button>
                )}
              </div>
              {open === key && options.length > 0 && (
                <div className="mt-2 flex flex-wrap justify-end gap-2">
                  {options.map((o) => (
                    <Button
                      key={o.label}
                      size="sm"
                      variant="outline"
                      disabled={!enabled}
                      className="font-mono"
                      onClick={() => {
                        setOpen(null)
                        onBuy(unlockBuyMessage(u, o))
                      }}
                    >
                      {o.label}
                    </Button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {hasPeriodData && <p className="mt-1 text-xs text-muted-foreground">Buybacks and burns: last 30 days</p>}
    </div>
  )
}
