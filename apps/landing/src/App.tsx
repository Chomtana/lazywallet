import { Audience } from './components/Audience'
import { Hero } from './components/Hero'
import { HowItWorks } from './components/HowItWorks'

const WALLET_URL: string = import.meta.env.VITE_WALLET_URL ?? 'http://localhost:5174'

export default function App() {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <span aria-hidden className="size-8 rounded-full bg-[radial-gradient(circle_at_35%_32%,#f1ffd9,#c6ff5e_45%,#b6ff3b_75%,#a6ee2c)] shadow-[0_0_18px_4px_rgba(182,255,59,0.35)]" />
          <span className="text-lg font-semibold tracking-tight">LazyWallet</span>
        </div>
        <a href={WALLET_URL} className="rounded-full border px-4 py-1.5 text-sm hover:border-primary">
          Launch
        </a>
      </header>
      <main>
        <Hero walletUrl={WALLET_URL} />
        <Audience />
        <HowItWorks />
      </main>
      <footer className="mx-auto max-w-6xl border-t px-4 py-8 text-sm text-muted-foreground">
        LazyWallet · Hackathon project · Sandbox demo on an Ethereum mainnet fork
      </footer>
    </div>
  )
}
