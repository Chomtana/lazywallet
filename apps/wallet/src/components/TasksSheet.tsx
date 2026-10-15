import { Repeat } from 'lucide-react'
import { formatUnits } from 'viem'
import { Badge } from '@/components/ui/badge'
import { BOTTOM_SHEET } from '@/components/sheet-styles'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { durationLabel, orderStatus, type ScheduledOrder } from '@/chain/scheduler'
import { formatAmount } from '@/lib/format'

type Props = { open: boolean; onOpenChange: (v: boolean) => void; orders: ScheduledOrder[]; loading: boolean }

export function TasksSheet({ open, onOpenChange, orders, loading }: Props) {
  const now = Math.floor(Date.now() / 1000)
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className={BOTTOM_SHEET}>
        <SheetHeader>
          <SheetTitle>Scheduled tasks</SheetTitle>
          <SheetDescription>Scheduled swaps run on-chain — this tab doesn’t need to stay open. To cancel one, ask in chat.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {orders.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {loading ? 'Loading…' : 'No scheduled swaps yet. Try “Swap 10 USDC to AVAX every minute, 3 times”.'}
            </p>
          ) : (
            <ul className="divide-y">
              {orders.map((o) => {
                const status = orderStatus(o, now)
                const amount = formatAmount(Number(formatUnits(o.amountIn, o.tokenIn.decimals)))
                return (
                  <li key={`${o.chainId}-${o.id}`} className="flex items-center gap-3 py-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                      <Repeat className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        <span className="font-mono">{amount}</span> {o.tokenIn.symbol} → {o.tokenOut.symbol}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {o.count > 1 ? `Every ${durationLabel(o.interval)} · ` : ''}
                        {o.executed}/{o.count} done · {o.network}
                      </p>
                    </div>
                    <Badge variant={status.state === 'active' ? 'default' : 'secondary'}>{status.label}</Badge>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
