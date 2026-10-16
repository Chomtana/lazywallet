import { initials } from '@/lib/tokenList'
import { cn } from '@/lib/utils'

type Props = { network: string; size?: number; className?: string }

// Small inline chain marks — no image fetch. Unknown networks get a muted initials circle.
export function ChainIcon({ network, size = 16, className }: Props) {
  const key = network.trim().toLowerCase()
  if (key === 'ethereum') {
    return (
      <svg role="img" aria-label="Ethereum" viewBox="0 0 32 32" width={size} height={size} className={cn('shrink-0', className)}>
        <title>Ethereum</title>
        <circle cx="16" cy="16" r="16" fill="#627EEA" />
        <path fill="#fff" fillOpacity=".6" d="M16.5 4v8.87l7.5 3.35z" />
        <path fill="#fff" d="M16.5 4 9 16.22l7.5-3.35z" />
        <path fill="#fff" fillOpacity=".6" d="M16.5 21.97V28L24 17.62z" />
        <path fill="#fff" d="M16.5 28v-6.03L9 17.62z" />
        <path fill="#fff" fillOpacity=".2" d="m16.5 20.57 7.5-4.35-7.5-3.35z" />
        <path fill="#fff" fillOpacity=".6" d="m9 16.22 7.5 4.35v-7.7z" />
      </svg>
    )
  }
  if (key === 'avalanche') {
    return (
      <svg role="img" aria-label="Avalanche" viewBox="0 0 32 32" width={size} height={size} className={cn('shrink-0', className)}>
        <title>Avalanche</title>
        <circle cx="16" cy="16" r="16" fill="#E84142" />
        <path fill="#fff" d="M20.5 16.6c.5-.86 1.3-.86 1.8 0l3.14 5.5c.5.86.09 1.56-.9 1.56h-6.32c-.99 0-1.4-.7-.9-1.56zM14.45 6.03c.5-.86 1.29-.86 1.79 0l.7 1.25 1.64 2.9c.4.82.4 1.79 0 2.61l-5.5 9.54a2.6 2.6 0 0 1-2.04 1.2H6.47c-1 0-1.4-.69-.9-1.55z" />
      </svg>
    )
  }
  return (
    <span
      role="img"
      aria-label={network}
      title={network}
      style={{ width: size, height: size, fontSize: Math.max(6, size * 0.4) }}
      className={cn('inline-flex shrink-0 items-center justify-center rounded-full bg-muted font-semibold text-muted-foreground', className)}
    >
      {initials(network)}
    </span>
  )
}
