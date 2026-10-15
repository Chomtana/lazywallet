import { Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { hostOf } from '@/lib/format'
import type { ConfirmState, TxDraft } from '@/types'

type Props = { tx: TxDraft; state: ConfirmState; onApprove: () => void; onReject: () => void }

const BADGE: Record<Exclude<ConfirmState, 'waiting'>, string> = {
  approved: 'Approved',
  rejected: 'Rejected',
  expired: 'Expired — ask again',
}

export function ConfirmCard({ tx, state, onApprove, onReject }: Props) {
  return (
    <div className="rounded-2xl border bg-card p-4">
      {tx.dapp && (
        <div className="mb-3 flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-full bg-secondary text-lg">{tx.dapp.icon}</span>
          <div className="min-w-0">
            <p className="font-medium">{tx.dapp.name}</p>
            <p className="truncate text-xs text-muted-foreground">{hostOf(tx.dapp.url)}</p>
          </div>
        </div>
      )}
      <p className="font-semibold">{tx.title}</p>
      {tx.explanation && (
        <p className="mt-2 rounded-xl bg-secondary p-3 text-sm">
          <Sparkles className="mr-1.5 inline size-3.5 text-primary" />
          {tx.explanation}
        </p>
      )}
      <dl className="mt-3 space-y-2 text-sm">
        {tx.rows.map((r) => (
          <div key={r.label} className="flex justify-between gap-4">
            <dt className="text-muted-foreground">{r.label}</dt>
            <dd className="text-right font-mono">{r.value}</dd>
          </div>
        ))}
      </dl>
      {tx.steps && tx.steps.length > 1 && (
        <div className="mt-3 rounded-xl bg-secondary p-3">
          <p className="text-xs font-medium text-muted-foreground">Steps (one tap runs them in order)</p>
          <ol className="mt-1 space-y-0.5 text-sm">
            {tx.steps.map((s, i) => (
              <li key={i}>
                {i + 1}. {s.label}
              </li>
            ))}
          </ol>
        </div>
      )}
      {state === 'waiting' ? (
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Button variant="secondary" onClick={onReject}>
            Reject
          </Button>
          <Button onClick={onApprove}>Approve</Button>
        </div>
      ) : (
        <Badge variant={state === 'approved' ? 'default' : 'secondary'} className="mt-4">
          {BADGE[state]}
        </Badge>
      )}
    </div>
  )
}
