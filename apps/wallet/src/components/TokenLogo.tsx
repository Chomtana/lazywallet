import { useState } from 'react'
import { initials } from '@/lib/tokenList'
import { cn } from '@/lib/utils'

// A token's logo, or its initials when there's none or the image fails to load.
export function TokenLogo({ src, symbol, className = 'size-8' }: { src?: string | null; symbol: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
        className={cn('shrink-0 rounded-full bg-muted object-cover', className)}
      />
    )
  }
  return (
    <span aria-hidden className={cn('flex shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-muted-foreground', className)}>
      {initials(symbol)}
    </span>
  )
}
