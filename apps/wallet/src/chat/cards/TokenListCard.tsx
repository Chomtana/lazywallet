import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChainIcon } from '@/components/ChainIcon'
import { TokenLogo } from '@/components/TokenLogo'
import { buyMessage, buyOptions, changeTone, formatChange, formatPrice, liquidityLine, spansNetworks } from '@/lib/tokenList'
import { cn } from '@/lib/utils'
import type { TrendingToken } from '@/types'

type Props = { title: string; items: TrendingToken[]; enabled: boolean; onBuy: (text: string) => void }

const TONE = { up: 'text-primary', down: 'text-destructive', flat: 'text-muted-foreground' }

export function TokenListCard({ title, items, enabled, onBuy }: Props) {
  const [open, setOpen] = useState<string | null>(null) // key of the row whose Buy chips are showing
  const showNetwork = spansNetworks(items)
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="font-semibold">{title}</p>
      <ul className="mt-2 divide-y">
        {items.map((t) => {
          const key = `${t.network}:${t.address}`
          const options = t.buyable ? buyOptions(t.network) : []
          return (
            <li key={key} className="py-2.5">
              <div className={cn('flex items-center gap-3', !t.buyable && 'opacity-50')}>
                <TokenLogo src={t.image} symbol={t.symbol} />
                <div className="min-w-0 flex-1">
                  <p className="flex items-baseline gap-1.5">
                    <span className="font-semibold">{t.symbol}</span>
                    <span className="truncate text-sm text-muted-foreground">{t.name}</span>
                  </p>
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="truncate">{liquidityLine(t)}</span>
                    {showNetwork && <ChainIcon network={t.network} size={14} />}
                  </p>
                  {t.note && (
                    <Badge variant="secondary" className="mt-1">
                      {t.note}
                    </Badge>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <span className="block font-mono text-sm">{formatPrice(t.priceUsd)}</span>
                  <span className={cn('block font-mono text-xs', TONE[changeTone(t.change24h)])}>{formatChange(t.change24h)}</span>
                </div>
                {options.length > 0 && (
                  <Button
                    className="h-9 px-5 font-semibold"
                    disabled={!enabled}
                    onClick={() => setOpen(open === key ? null : key)}
                  >
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
                        onBuy(buyMessage(t, o))
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
    </div>
  )
}
