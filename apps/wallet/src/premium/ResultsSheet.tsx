import { useEffect } from 'react'
import { Bot, Volume2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BOTTOM_SHEET } from '@/components/sheet-styles'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { formatUsd } from '@/lib/format'
import { speak, stopSpeaking } from '@/voice/speech'
import { RESULTS, type HuntProtocol, type PlanId } from './plans'

type Props = { open: boolean; onOpenChange: (v: boolean) => void; plan: PlanId; speakEnabled: boolean }

const STATUS: Record<HuntProtocol['status'], string> = {
  farming: 'bg-primary/15 text-primary',
  qualified: 'bg-secondary text-foreground',
  'snapshot soon': 'bg-amber-400/15 text-amber-300',
}

// Overnight report: an AI summary (read aloud on open), headline stats, positions per protocol and the bot's log.
export function ResultsSheet({ open, onOpenChange, plan, speakEnabled }: Props) {
  const r = RESULTS[plan]

  useEffect(() => {
    if (!open) return
    speak(r.summary, speakEnabled)
    return stopSpeaking
  }, [open, r.summary, speakEnabled])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className={BOTTOM_SHEET}>
        <SheetHeader>
          <SheetTitle>Hunting results</SheetTitle>
          <SheetDescription>Last 24 hours</SheetDescription>
        </SheetHeader>
        <div className="space-y-5 overflow-y-auto px-4 pb-6">
          <div className="rounded-2xl border border-primary/40 bg-primary/10 p-4">
            <div className="mb-2 flex items-center gap-2">
              <Bot className="size-4 text-primary" />
              <p className="flex-1 text-sm font-medium">AI summary</p>
              <Button variant="ghost" size="icon" className="size-8 rounded-full" aria-label="Play summary" onClick={() => speak(r.summary, true)}>
                <Volume2 />
              </Button>
            </div>
            <p className="text-sm leading-relaxed">{r.summary}</p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {r.stats.map((s) => (
              <div key={s.label} className="rounded-2xl border bg-card p-3">
                <p className="font-mono text-lg font-semibold">{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>

          <section>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Positions</h3>
            <ul className="divide-y rounded-2xl border bg-card">
              {r.protocols.map((p) => (
                <li key={p.name} className="flex items-center gap-3 p-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold">
                    {p.name.slice(0, 2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 font-medium">
                      {p.name}
                      <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', STATUS[p.status])}>{p.status}</span>
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {[p.kind, p.network, p.activity].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="font-mono text-sm">≈ {formatUsd(p.estUsd)}</p>
                    <p className="font-mono text-xs text-muted-foreground">{p.points}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Bot activity</h3>
            <ul className="space-y-2 text-sm">
              {r.log.map((l) => (
                <li key={l.when + l.text} className="flex gap-3">
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">{l.when}</span>
                  <span>{l.text}</span>
                </li>
              ))}
            </ul>
          </section>
          <p className="text-center text-xs text-muted-foreground">Estimates — final airdrop values are set by each project.</p>
        </div>
      </SheetContent>
    </Sheet>
  )
}
