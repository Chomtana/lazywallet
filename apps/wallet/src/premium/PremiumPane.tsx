import { Bot, RefreshCw, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { planOf, type Subscription } from './plans'

type Props = {
  subscription: Subscription | null
  onChoosePlan: () => void
  onResults: () => void
}

// Highlighted strip under the composer: an upsell, or the live hunting plan with its results.
export function PremiumPane({ subscription, onChoosePlan, onResults }: Props) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-primary/40 bg-gradient-to-r from-primary/15 via-primary/5 to-transparent px-3 py-2">
      {subscription ? (
        <>
          <span className="relative flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary">
            <Bot className="size-4" />
            <span className="absolute -right-0.5 -bottom-0.5 size-2.5 animate-pulse rounded-full bg-primary ring-2 ring-background" />
          </span>
          <p className="min-w-0 flex-1 text-sm font-medium">{planOf(subscription.plan).paneTitle}</p>
          <Button variant="ghost" size="icon" className="size-8 shrink-0 rounded-full" aria-label="Change plan" onClick={onChoosePlan}>
            <RefreshCw />
          </Button>
          <Button size="sm" className="shrink-0 rounded-full" onClick={onResults}>
            Hunting Results
          </Button>
        </>
      ) : (
        <>
          <Sparkles className="size-4 shrink-0 text-primary" />
          <p className="min-w-0 flex-1 text-sm">
            Want to <span className="font-semibold text-primary">earn</span> while you sleep?
          </p>
          <Button size="sm" className="shrink-0 rounded-full" onClick={onChoosePlan}>
            Enable Auto Airdrop Hunting
          </Button>
        </>
      )}
    </div>
  )
}
