import { cn } from '@/lib/utils'

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-4', className)}>
      <span aria-hidden className="size-8 rounded-full bg-[radial-gradient(circle_at_35%_32%,#f1ffd9,#c6ff5e_45%,#b6ff3b_75%,#a6ee2c)] shadow-[0_0_18px_4px_rgba(182,255,59,0.35)]" />
      <span className="text-2xl font-semibold tracking-tight">LazyWallet</span>
    </div>
  )
}
