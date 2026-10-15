import { useState } from 'react'
import { Check, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BOTTOM_SHEET } from '@/components/sheet-styles'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { formatUsd } from '@/lib/format'
import { DEFAULT_PLAN, PERKS, PLANS, planOf, type PlanId } from './plans'

type Props = {
  open: boolean
  onOpenChange: (v: boolean) => void
  current: PlanId | null
  onSubscribe: (plan: PlanId) => void
}

// Pick a plan, then confirm the first month's charge — both inside the sheet, never in chat.
export function PlanSheet({ open, onOpenChange, current, onSubscribe }: Props) {
  const [selected, setSelected] = useState<PlanId>(current ?? DEFAULT_PLAN)
  const [confirming, setConfirming] = useState(false)
  const plan = planOf(selected)

  function change(v: boolean) {
    if (v) {
      setSelected(current ?? DEFAULT_PLAN)
      setConfirming(false)
    }
    onOpenChange(v)
  }

  return (
    <Sheet open={open} onOpenChange={change}>
      <SheetContent side="bottom" className={BOTTOM_SHEET}>
        <SheetHeader>
          <SheetTitle>{confirming ? 'Confirm subscription' : 'Auto airdrop hunting'}</SheetTitle>
          <SheetDescription>
            {confirming ? 'Check the details before you start.' : 'Your agent hunts airdrops around the clock — you keep the rewards.'}
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-4 overflow-y-auto px-4 pb-6">
          {confirming ? (
            <>
              <dl className="space-y-2 rounded-2xl border bg-card p-4 text-sm">
                <Row label="Plan" value={plan.name} />
                <Row label="Billed" value={`${formatUsd(plan.priceUsd)} / month`} />
                <Row label="Charged now" value={`${formatUsd(plan.priceUsd)} USDC`} strong />
                <Row label="Recommended balance" value={`${formatUsd(plan.minWalletUsd)} in wallet`} />
              </dl>
              <p className="text-xs text-muted-foreground">
                The first month is taken from your wallet now. Cancel any time — the plan runs until the end of the paid month.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="secondary" onClick={() => setConfirming(false)}>
                  Back
                </Button>
                <Button
                  onClick={() => {
                    onSubscribe(selected)
                    onOpenChange(false)
                  }}
                >
                  Pay {formatUsd(plan.priceUsd)} & start
                </Button>
              </div>
            </>
          ) : (
            <>
              <div role="radiogroup" className="space-y-2">
                {PLANS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    role="radio"
                    aria-checked={selected === p.id}
                    onClick={() => setSelected(p.id)}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-2xl border bg-card p-4 text-left transition',
                      selected === p.id ? 'border-primary ring-1 ring-primary' : 'hover:border-primary/50',
                    )}
                  >
                    <span
                      className={cn(
                        'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border',
                        selected === p.id && 'border-primary bg-primary text-primary-foreground',
                      )}
                    >
                      {selected === p.id && <Check className="size-3" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="font-medium">
                          {p.name}
                          {current === p.id && <span className="ml-2 text-xs text-primary">Current</span>}
                        </span>
                        <span className="shrink-0 font-mono">
                          {formatUsd(p.priceUsd)}
                          <span className="text-xs text-muted-foreground">/mo</span>
                        </span>
                      </span>
                      <span className="mt-1 block text-sm text-muted-foreground">{p.blurb}</span>
                      <span className="mt-1 block text-xs text-muted-foreground">Needs {formatUsd(p.minWalletUsd)} in wallet</span>
                    </span>
                  </button>
                ))}
              </div>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                {PERKS.map((perk) => (
                  <li key={perk} className="flex items-center gap-2">
                    <ShieldCheck className="size-4 shrink-0 text-primary" />
                    {perk}
                  </li>
                ))}
              </ul>
              <Button className="w-full" disabled={current === selected} onClick={() => setConfirming(true)}>
                {current === selected ? 'Your current plan' : `Continue with ${plan.name}`}
              </Button>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn('text-right', strong && 'font-mono font-semibold text-primary')}>{value}</dd>
    </div>
  )
}
