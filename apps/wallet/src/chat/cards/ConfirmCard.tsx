import { ArrowDown, ChevronRight, Sparkles, TriangleAlert } from 'lucide-react'
import { ChainIcon } from '@/components/ChainIcon'
import { TokenLogo } from '@/components/TokenLogo'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { hostOf } from '@/lib/format'
import type { ConfirmState, SummaryToken, TxDraft, TxSummary } from '@/types'
import { stepsHeading, summaryFooter, usdLabel } from './summary'

type Props = { tx: TxDraft; state: ConfirmState; onApprove: () => void; onReject: () => void }

const BADGE: Record<Exclude<ConfirmState, 'waiting'>, string> = {
  approved: 'Approved',
  rejected: 'Rejected',
  expired: 'Expired — ask again',
}

function Rows({ rows }: { rows: TxDraft['rows'] }) {
  return (
    <dl className="space-y-2 text-sm">
      {rows.map((r) => (
        <div key={r.label} className="flex justify-between gap-4">
          <dt className="text-muted-foreground">{r.label}</dt>
          <dd className="min-w-0 text-right font-mono wrap-anywhere">{r.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Steps({ steps }: { steps: NonNullable<TxDraft['steps']> }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{stepsHeading(steps.length)}</p>
      <ol className="mt-1 space-y-0.5 text-sm">
        {steps.map((s, i) => (
          <li key={i}>
            {i + 1}. {s.label}
          </li>
        ))}
      </ol>
    </div>
  )
}

function TokenLine({ label, token, note }: { label: string; token: SummaryToken; note?: string | null }) {
  const usd = usdLabel(token.usd)
  return (
    <div className="flex items-center gap-3">
      <TokenLogo src={token.logo} symbol={token.symbol} className="size-9" />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="truncate">
          <span className="font-mono text-xl font-semibold">{token.amount}</span> <span className="font-medium">{token.symbol}</span>
        </p>
        {note && <p className="text-xs text-muted-foreground">{note}</p>}
      </div>
      {usd && <span className="shrink-0 font-mono text-sm text-muted-foreground">{usd}</span>}
    </div>
  )
}

function Down() {
  return (
    <div className="flex justify-center py-1">
      <span className="flex size-6 items-center justify-center rounded-full border bg-card">
        <ArrowDown className="size-3.5 text-muted-foreground" />
      </span>
    </div>
  )
}

function Summary({ s }: { s: TxSummary }) {
  return (
    <>
      <div className="mt-3 rounded-xl bg-secondary p-3">
        <TokenLine label={s.kind === 'farm' ? 'You deposit' : 'You pay'} token={s.pay} />
        <Down />
        {s.swap && (
          <>
            <div className="flex items-center gap-3">
              <TokenLogo src={s.swap.logo} symbol={s.swap.symbol} className="size-7" />
              <div className="min-w-0 flex-1">
                <p className="text-xs text-muted-foreground">Swap · via {s.swap.via}</p>
                <p className="truncate">
                  <span className="font-mono">{s.swap.amount}</span> <span className="font-medium">{s.swap.symbol}</span>
                </p>
              </div>
            </div>
            <Down />
          </>
        )}
        <TokenLine label="You get" token={s.receive} note={s.receive.note} />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{summaryFooter(s)}</p>
      {s.warning && (
        <p className="mt-1 flex items-center gap-1.5 text-xs text-destructive">
          <TriangleAlert className="size-3.5" /> {s.warning}
        </p>
      )}
    </>
  )
}

export function ConfirmCard({ tx, state, onApprove, onReject }: Props) {
  const s = tx.summary
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
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold">{tx.title}</p>
        {s && (
          <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
            <ChainIcon network={s.network} size={14} />
            {s.network}
          </span>
        )}
      </div>
      {tx.explanation && (
        <p className="mt-2 rounded-xl bg-secondary p-3 text-sm">
          <Sparkles className="mr-1.5 inline size-3.5 text-primary" />
          {tx.explanation}
        </p>
      )}
      {s ? (
        <>
          <Summary s={s} />
          <details className="group mt-3 rounded-xl border">
            <summary className="flex cursor-pointer list-none items-center gap-1 px-3 py-2 text-sm text-muted-foreground [&::-webkit-details-marker]:hidden">
              <ChevronRight className="size-4 transition-transform group-open:rotate-90" /> Details
            </summary>
            <div className="space-y-3 px-3 pb-3">
              {tx.steps && tx.steps.length > 0 && <Steps steps={tx.steps} />}
              <Rows rows={tx.rows} />
            </div>
          </details>
        </>
      ) : (
        <>
          <div className="mt-3">
            <Rows rows={tx.rows} />
          </div>
          {tx.steps && tx.steps.length > 1 && (
            <div className="mt-3 rounded-xl bg-secondary p-3">
              <Steps steps={tx.steps} />
            </div>
          )}
        </>
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
