import { CheckCircle2, Loader2 } from 'lucide-react'
import { shortAddress } from '@/lib/format'

type Props = { state: 'pending' | 'success'; text: string; hash?: string }

export function StatusCard({ state, text, hash }: Props) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border bg-card p-4">
      {state === 'pending' ? (
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      ) : (
        <CheckCircle2 className="size-5 text-primary" />
      )}
      <div className="min-w-0">
        <p>{text}</p>
        {hash && <p className="truncate font-mono text-xs text-muted-foreground">Tx {shortAddress(hash)}</p>}
      </div>
    </div>
  )
}
