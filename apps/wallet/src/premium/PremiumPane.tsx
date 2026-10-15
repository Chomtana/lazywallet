import { Bot, RefreshCw, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { planOf, type Subscription } from './plans'

type Props = {
  subscription: Subscription | null
  onChoosePlan: () => void
  onResults: () => void
}

const ACTION = 'h-10 rounded-full text-base'

// Highlighted strip under the composer: a line of text, then its buttons — an upsell, or the live plan and its results.
export function PremiumPane({ subscription, onChoosePlan, onResults }: Props) {
  return (
    <div className="space-y-2 rounded-2xl border border-primary/40 bg-gradient-to-r from-primary/15 via-primary/5 to-transparent p-3">
      {subscription ? (
        <>
          <p className="flex items-center justify-center gap-2 text-sm font-medium">
            <Bot className="size-4 shrink-0 text-primary" />
            {planOf(subscription.plan).paneTitle}
            <span className="size-2 shrink-0 animate-pulse rounded-full bg-primary" aria-label="Running" />
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="icon" className="size-10 shrink-0 rounded-full" aria-label="Change plan" onClick={onChoosePlan}>
              <RefreshCw />
            </Button>
            <Button className={`flex-1 ${ACTION}`} onClick={onResults}>
              Airdrop Hunting Results
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="flex items-center justify-center gap-2 text-sm">
            <Sparkles className="size-4 shrink-0 text-primary" />
            <span>
              Want to <span className="font-semibold text-primary">earn</span> while you sleep?
            </span>
          </p>
          <Button className={`w-full ${ACTION}`} onClick={onChoosePlan}>
            Enable Auto Airdrop Hunting
          </Button>
        </>
      )}
    </div>
  )
}
