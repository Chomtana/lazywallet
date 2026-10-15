import { useEffect, useState } from 'react'
import { Mic } from 'lucide-react'

const PHASE_MS = 2200
const BARS = Array.from({ length: 24 }, (_, i) => i)

export function VoiceDemo() {
  const [phase, setPhase] = useState(0)

  useEffect(() => {
    const t = window.setInterval(() => setPhase((p) => (p + 1) % 3), PHASE_MS)
    return () => window.clearInterval(t)
  }, [])

  return (
    <div className="mx-auto w-full max-w-sm space-y-4 rounded-3xl border bg-card p-5 shadow-[0_0_80px_-20px_rgba(182,255,59,0.35)]">
      <div className="flex h-14 items-center justify-center gap-1" aria-hidden>
        {BARS.map((i) => (
          <span
            key={i}
            className="w-1 origin-center rounded-full bg-primary transition-opacity motion-safe:animate-[wave_1s_ease-in-out_infinite]"
            style={{ height: `${20 + ((i * 37) % 28)}px`, animationDelay: `${i * 60}ms`, opacity: phase === 0 ? 1 : 0.2 }}
          />
        ))}
      </div>
      <div className={`flex justify-end transition-opacity duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <p className="rounded-2xl rounded-br-md bg-primary px-4 py-2 text-sm text-primary-foreground">
          <Mic className="mr-1 inline size-3.5 align-[-2px]" />
          Swap 100 USDC to ETH
        </p>
      </div>
      <div className={`rounded-2xl border bg-background p-4 text-sm transition-opacity duration-500 ${phase === 2 ? 'opacity-100' : 'opacity-0'}`}>
        <p className="font-semibold">Swap 100 USDC → ETH</p>
        <dl className="mt-2 space-y-1">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">You receive</dt>
            <dd className="font-mono">≈ 0.0311562 ETH</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Route</dt>
            <dd className="font-mono">Uniswap v3</dd>
          </div>
        </dl>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <span className="rounded-full bg-secondary py-1.5 text-center">Reject</span>
          <span className="rounded-full bg-primary py-1.5 text-center font-medium text-primary-foreground">Approve</span>
        </div>
      </div>
    </div>
  )
}
