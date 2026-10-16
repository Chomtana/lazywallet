import { Bot, CheckCircle2 } from 'lucide-react'
import { formatUsd } from '@/lib/format'
import { planOf, type PlanId } from '@/premium/plans'

// Shown in chat after a plan is confirmed in the plan sheet.
export function SubscriptionCard({ plan, chargedUsd, renews }: { plan: PlanId; chargedUsd: number; renews: string }) {
  const p = planOf(plan)
  return (
    <div className="rounded-2xl border border-primary/40 bg-card p-4">
      <div className="flex items-center gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
          <Bot className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium">Subscribed to {p.name}</p>
          <p className="text-sm text-muted-foreground">Hunting starts now and runs 24/7.</p>
        </div>
        <CheckCircle2 className="size-5 shrink-0 text-primary" />
      </div>
      <dl className="mt-3 space-y-1 border-t pt-3 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Paid (first month)</dt>
          <dd className="font-mono">{formatUsd(chargedUsd)} USDC</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Renews</dt>
          <dd>{renews}</dd>
        </div>
      </dl>
    </div>
  )
}
