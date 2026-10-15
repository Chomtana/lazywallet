import { Mic } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="flex size-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Mic className="size-4" />
      </span>
      <span className="text-lg font-semibold tracking-tight">LazyWallet</span>
    </div>
  )
}
