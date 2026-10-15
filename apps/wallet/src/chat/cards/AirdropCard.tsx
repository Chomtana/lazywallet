import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { AirdropItem } from '@/types'
import { AMOUNTS_USDC, buyReply, farmReply, statusLabel, tvlLabel } from './airdrops'

type Props = { title: string; items: AirdropItem[]; enabled: boolean; onSend: (text: string) => void }

export function AirdropCard({ title, items, enabled, onSend }: Props) {
  // Which row's amount chips are open: `${id}:farm` or `${id}:buy`.
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="font-semibold">{title}</p>
      <ul className="mt-2 divide-y">
        {items.map((a) => {
          const action = a.farm ? 'farm' : a.buy ? 'buy' : null
          const key = `${a.id}:${action}`
          return (
            <li key={a.id} className="py-3">
              <div className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{a.name}</span>
                    <Badge variant={a.category === 'rwa' ? 'default' : 'secondary'}>{a.category === 'rwa' ? 'RWA' : 'other'}</Badge>
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {a.networks.join(' · ')} · <span className={cn(a.status === 'live' ? 'text-primary' : 'text-muted-foreground')}>{statusLabel(a.status)}</span>
                  </span>
                  <span className="mt-1 block text-sm">{a.action}</span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block font-mono text-xs text-muted-foreground">{tvlLabel(a.tvlUsd)}</span>
                  {action && (
                    <Button size="sm" variant="secondary" className="mt-1.5" disabled={!enabled} onClick={() => setOpen(open === key ? null : key)}>
                      {action === 'farm' ? 'Farm' : `Buy ${a.buy?.symbol}`}
                    </Button>
                  )}
                </span>
              </div>
              {action && open === key && (
                <div className="mt-2 flex justify-end gap-2">
                  {AMOUNTS_USDC.map((usdc) => (
                    <Button
                      key={usdc}
                      size="sm"
                      variant="outline"
                      className="font-mono"
                      disabled={!enabled}
                      onClick={() => {
                        setOpen(null)
                        onSend(a.farm ? farmReply(a.farm, usdc) : buyReply(a.buy!, usdc))
                      }}
                    >
                      ${usdc}
                    </Button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">Points only count on real mainnet. This Sandbox is a demo.</p>
    </div>
  )
}
