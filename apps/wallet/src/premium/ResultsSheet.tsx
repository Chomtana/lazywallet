import { useEffect } from 'react'
import { Bot, Volume2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BOTTOM_SHEET } from '@/components/sheet-styles'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { speak, stopSpeaking } from '@/voice/speech'
import { RESULTS, type PlanId } from './plans'

const compactUsd = (n: number) => `$${Intl.NumberFormat('en-US', { notation: 'compact' }).format(n)}`

type Props = { open: boolean; onOpenChange: (v: boolean) => void; plan: PlanId; speakEnabled: boolean }

// Overnight report: an AI summary (read aloud on open), headline stats, then points (and perp/RWA volume) per project.
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

          <div className="flex gap-2">
            {r.stats.map((s) => (
              <div key={s.label} className="flex-1 rounded-2xl border bg-card p-3">
                <p className="font-mono text-lg font-semibold">{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>

          {r.sections.map((sec) => (
            <section key={sec.title}>
              <div className="mb-2 flex px-1 text-xs text-muted-foreground">
                <span className="flex-1 font-medium">{sec.title}</span>
                {sec.showVolume && <span className="w-20 text-right">Volume 24h</span>}
                <span className="w-28 text-right">Points</span>
              </div>
              <ul className="divide-y rounded-2xl border bg-card">
                {sec.projects.map((p) => (
                  <li key={p.name} className="flex items-center gap-3 p-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold">
                      {p.name.slice(0, 2)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{p.name}</p>
                      <p className="truncate text-xs text-muted-foreground">{[p.kind, p.network].filter(Boolean).join(' · ')}</p>
                    </div>
                    {sec.showVolume && <p className="w-20 shrink-0 text-right font-mono text-sm">{p.volumeUsd ? compactUsd(p.volumeUsd) : '—'}</p>}
                    <div className="w-28 shrink-0 text-right">
                      <p className="font-mono text-sm">
                        {p.points.toLocaleString('en-US')} <span className="text-xs text-muted-foreground">{p.unit}</span>
                      </p>
                      <p className="font-mono text-xs text-primary">+{p.pointsToday.toLocaleString('en-US')} today</p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          <p className="text-center text-xs text-muted-foreground">Points as reported by each project.</p>
        </div>
      </SheetContent>
    </Sheet>
  )
}
