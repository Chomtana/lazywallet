import { ArrowRight } from 'lucide-react'
import { VoiceDemo } from './VoiceDemo'

export function Hero({ walletUrl }: { walletUrl: string }) {
  return (
    <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 md:grid-cols-2 md:py-28">
      <div className="space-y-6">
        <p className="inline-flex rounded-full border px-3 py-1 text-xs text-muted-foreground">Voice-powered AI wallet</p>
        <h1 className="text-5xl font-semibold tracking-tight md:text-6xl">Just say it.</h1>
        <p className="max-w-md text-lg text-muted-foreground">
          Check balances, send, swap and automate trades by talking to your wallet. You approve every transaction.
        </p>
        <a
          href={walletUrl}
          className="inline-flex h-12 items-center gap-2 rounded-full bg-primary px-6 font-medium text-primary-foreground transition hover:opacity-90"
        >
          Launch Wallet <ArrowRight className="size-4" />
        </a>
      </div>
      <VoiceDemo />
    </section>
  )
}
